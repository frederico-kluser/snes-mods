-- snesfab harness — roda dentro do MesenCE em modo `--testRunner` (headless).
--
-- Lê o job (tabela Lua gerada pelo Python) do caminho em $SNESFAB_JOB e:
--   1. carrega o savestate (dentro de um callback de execução, como o Mesen exige);
--   2. injeta o macro de input frame a frame (evento inputPolled, porta 1);
--   3. grava frames (RGB24 cru), traço de RAM por frame (CSV), dumps de WRAM, sondas de
--      memória (leitura/escrita/execução com registradores da CPU) e savestates pedidos;
--   4. escreve result.json e termina com emu.stop(0) (ou ≠0 em erro).
-- Requer "Allow access to I/O and OS functions" (settings.json → Debug.ScriptWindow.AllowIoOsAccess).

local JOB_PATH = os.getenv("SNESFAB_JOB")
if not JOB_PATH then
  emu.log("SNESFAB_JOB ausente")
  emu.stop(90)
  return
end

local loaded, job = pcall(dofile, JOB_PATH)
if not loaded or type(job) ~= "table" then
  emu.log("job inválido: " .. tostring(job))
  emu.stop(91)
  return
end

local OUT = job.out_dir
local MT_CPU = emu.memType.snesMemory
local CPU_SNES = emu.cpuType.snes

-- o Python passa nomes de memType ("snesWorkRam", "snesDebug", …); resolve-os aqui
for _, group in ipairs({ job.watch or {}, job.probes or {}, job.pokes or {} }) do
  for _, item in ipairs(group) do
    if type(item.mem) == "string" then
      local v = emu.memType[item.mem]
      if v == nil then
        emu.log("memType desconhecido: " .. item.mem)
        emu.stop(92)
        return
      end
      item.mem = v
    end
  end
end

local frame = 0          -- frames completos desde o início do cenário (após carregar o state)
local phase = "running"  -- loading → loaded → running → finished
local finished = false
local t_start = os.clock()

local logf = io.open(OUT .. "/harness.log", "w")
local function log(msg)
  logf:write(string.format("[%s f=%d] %s\n", phase, frame, msg))
  logf:flush()
end

local function json_str(s)
  s = tostring(s)
  s = s:gsub('\\', '\\\\'):gsub('"', '\\"'):gsub('\n', '\\n'):gsub('\r', '\\r'):gsub('\t', '\\t')
  s = s:gsub('[%z\1-\31]', function(c) return string.format('\\u%04x', c:byte()) end)
  return '"' .. s .. '"'
end

-- ── saídas ──────────────────────────────────────────────────────────────────
local cap = job.capture or {}
local cap_every = cap.every or 0
local cap_start = cap.start or 0
local framesf, idxf, frames_offset, frames_captured = nil, nil, 0, 0
if cap_every > 0 then
  framesf = io.open(OUT .. "/frames.rgb", "wb")
  idxf = io.open(OUT .. "/frames_index.csv", "w")
  idxf:write("frame,width,height,offset\n")
end

local watches = job.watch or {}
local tracef = io.open(OUT .. "/trace.csv", "w")
do
  local cols = { "frame", "input" }
  for _, w in ipairs(watches) do cols[#cols + 1] = w.name end
  tracef:write(table.concat(cols, ","), "\n")
end

local probes = job.probes or {}
local probesf = (#probes > 0) and io.open(OUT .. "/probes.jsonl", "w") or nil

local wram_every = job.wram_every or 0
local wramf, wram_dumps = nil, 0
if wram_every > 0 then wramf = io.open(OUT .. "/wram.bin", "wb") end

-- ── input ───────────────────────────────────────────────────────────────────
local BTN = {
  { "b", 0x8000 }, { "y", 0x4000 }, { "select", 0x2000 }, { "start", 0x1000 },
  { "up", 0x0800 }, { "down", 0x0400 }, { "left", 0x0200 }, { "right", 0x0100 },
  { "a", 0x0080 }, { "x", 0x0040 }, { "l", 0x0020 }, { "r", 0x0010 },
}
local macro = job.macro or {}
local m_idx, m_base = 1, 0   -- cursor monotônico no macro
local cur_mask = 0

local function mask_for(f)
  while m_idx <= #macro and f >= m_base + macro[m_idx][1] do
    m_base = m_base + macro[m_idx][1]
    m_idx = m_idx + 1
  end
  if m_idx <= #macro then return macro[m_idx][2] end
  return 0
end

-- ── leitura de RAM ──────────────────────────────────────────────────────────
local function read_watch(w)
  if w.size == 1 then return emu.read(w.offset, w.mem, w.signed or false)
  elseif w.size == 2 then return emu.read16(w.offset, w.mem, w.signed or false)
  else return emu.read32(w.offset, w.mem, w.signed or false) end
end

local function dump_wram()
  local MT_WRAM = emu.memType.snesWorkRam
  local t = {}
  for base = 0, 0x1FFFF, 256 do
    for i = 0, 255 do t[i + 1] = emu.read(base + i, MT_WRAM, false) end
    wramf:write(string.char(table.unpack(t, 1, 256)))
  end
  wram_dumps = wram_dumps + 1
end

local function capture_frame()
  local buf = emu.getScreenBuffer()
  local size = emu.getScreenSize()
  local n = #buf
  local parts = {}
  for i = 1, n do
    local c = buf[i]
    parts[i] = string.char((c >> 16) & 0xFF, (c >> 8) & 0xFF, c & 0xFF)
  end
  local s = table.concat(parts)
  framesf:write(s)
  idxf:write(string.format("%d,%d,%d,%d\n", frame, size.width, size.height, frames_offset))
  frames_offset = frames_offset + #s
  frames_captured = frames_captured + 1
end

-- ── savestates (só podem ser criados/carregados num callback de execução da CPU principal) ──
local state_data = nil
local state_ok = nil
if job.state then
  local f = io.open(job.state, "rb")
  if not f then
    log("savestate não encontrado: " .. job.state)
  else
    state_data = f:read("a")
    f:close()
    phase = "loading"
  end
end

local save_queue = {}        -- caminhos a gravar no próximo callback de execução
local save_at = job.save_at or {}
local saves_done = {}
local exec_ref = nil

local function on_exec_any(address, value)
  if phase == "loading" then
    state_ok = emu.loadSavestate(state_data)
    phase = "loaded"
  elseif #save_queue > 0 then
    local data = emu.createSavestate()
    for _, p in ipairs(save_queue) do
      local f = io.open(p, "wb")
      f:write(data)
      f:close()
      saves_done[#saves_done + 1] = p
    end
    save_queue = {}
  end
end

local guarded  -- definido abaixo

local function exec_hook_on()
  if not exec_ref then
    exec_ref = emu.addMemoryCallback(guarded(on_exec_any), emu.callbackType.exec, 0, 0xFFFFFF, CPU_SNES, MT_CPU)
  end
end

local function exec_hook_off()
  -- nunca remover dentro do próprio callback de memória (invalida o iterador do Mesen)
  if exec_ref and phase ~= "loading" and #save_queue == 0 then
    emu.removeMemoryCallback(exec_ref, emu.callbackType.exec, 0, 0xFFFFFF, CPU_SNES, MT_CPU)
    exec_ref = nil
  end
end

-- ── sondas de memória ───────────────────────────────────────────────────────
local CB = { read = emu.callbackType.read, write = emu.callbackType.write, exec = emu.callbackType.exec }

local function register_probes()
  for i, p in ipairs(probes) do
    p.hits = 0
    p.max_hits = p.max_hits or 500
    local kind = p.kind
    local function cb(address, value)
      if phase ~= "running" then return end
      p.hits = p.hits + 1
      if p.hits <= p.max_hits then
        local c = emu.getCpuState(CPU_SNES)
        probesf:write(string.format(
          '{"probe":%d,"kind":"%s","frame":%d,"addr":%d,"value":%d,"k":%d,"pc":%d,"ps":%d,"a":%d,"x":%d,"y":%d,"dbr":%d,"d":%d,"sp":%d,"emu":%s}\n',
          i, kind, frame, address, value, c.k or 0, c.pc or 0, c.ps or 0, c.a or 0, c.x or 0, c.y or 0,
          c.dbr or 0, c.d or 0, c.sp or 0, tostring(c.emulationMode == true)))
      end
    end
    p.ref = emu.addMemoryCallback(guarded(cb), CB[kind], p.start, p.stop, CPU_SNES, p.mem)
  end
end

-- ── fim ─────────────────────────────────────────────────────────────────────
local function dump_cdl(path)
  -- flags por byte da ROM: 0x01 código, 0x02 dado, 0x04 alvo de salto, 0x08 entrada de sub-rotina,
  -- 0x10 X a 8 bits, 0x20 M a 8 bits (estes dois só no 1.º byte de cada instrução executada)
  local cdl = emu.getCdlData(emu.memType.snesPrgRom)
  local size = emu.getMemorySize(emu.memType.snesPrgRom)
  local f = io.open(path, "wb")
  local CH = 4096
  for base = 0, size - 1, CH do
    local last = math.min(base + CH - 1, size - 1)
    f:write(string.char(table.unpack(cdl, base, last)))
  end
  f:close()
end

local function finish(status, err)
  if finished then return end
  finished = true
  phase = "finished"
  if status == "ok" and job.cdl_out then
    local ok, e = pcall(dump_cdl, job.cdl_out)
    if not ok then status, err = "error", "falha no dump do CDL: " .. tostring(e) end
  end
  if framesf then framesf:close(); idxf:close() end
  tracef:close()
  if probesf then probesf:close() end
  if wramf then wramf:close() end
  local rom = emu.getRomInfo()
  local hits = {}
  for i, p in ipairs(probes) do hits[#hits + 1] = tostring(p.hits or 0) end
  local saves = {}
  for _, p in ipairs(saves_done) do saves[#saves + 1] = json_str(p) end
  local r = io.open(OUT .. "/result.json", "w")
  r:write("{\n")
  r:write('  "status": ', json_str(status), ',\n')
  r:write('  "error": ', err and json_str(err) or "null", ',\n')
  r:write('  "frames_run": ', frame, ',\n')
  r:write('  "frames_requested": ', job.frames, ',\n')
  r:write('  "state": ', job.state and json_str(job.state) or "null", ',\n')
  r:write('  "state_loaded": ', tostring(state_ok == true), ',\n')
  r:write('  "frames_captured": ', frames_captured, ',\n')
  r:write('  "wram_dumps": ', wram_dumps, ',\n')
  r:write('  "probe_hits": [', table.concat(hits, ", "), '],\n')
  r:write('  "saved_states": [', table.concat(saves, ", "), '],\n')
  r:write('  "rom_name": ', json_str(rom.name), ',\n')
  r:write('  "rom_sha1": ', json_str(rom.fileSha1Hash), ',\n')
  r:write('  "cpu_seconds": ', string.format("%.3f", os.clock() - t_start), '\n')
  r:write("}\n")
  r:close()
  log("fim: " .. status .. (err and (" — " .. err) or ""))
  logf:close()
  emu.stop(status == "ok" and 0 or 2)
end

guarded = function(fn)
  return function(...)
    if finished then return end
    local ok, err = pcall(fn, ...)
    if not ok then finish("error", tostring(err)) end
  end
end

-- ── eventos ─────────────────────────────────────────────────────────────────
local pokes = job.pokes or {}

local function on_input_polled()
  if phase ~= "running" then return end
  local m = mask_for(frame)
  local t = {}
  for _, p in ipairs(BTN) do t[p[1]] = (m & p[2]) ~= 0 end
  emu.setInput(t, 0)
  cur_mask = m
end

local function start_running()
  phase = "running"
  frame = 0
  register_probes()
  log("cenário iniciado" .. (job.state and (" (state ok=" .. tostring(state_ok) .. ")") or " (power-on)"))
end

local function on_end_frame()
  if phase == "loaded" then
    exec_hook_off()
    if state_ok ~= true then
      finish("error", "loadSavestate falhou (state de outra ROM/versão do Mesen?)")
      return
    end
    start_running()
    return
  end
  if phase ~= "running" then
    if phase == "saving_end" then
      if #save_queue == 0 then exec_hook_off(); finish("ok") end
    end
    return
  end

  -- frame `frame` acabou de ser emulado com o input cur_mask
  local row = { tostring(frame), tostring(cur_mask) }
  for _, w in ipairs(watches) do row[#row + 1] = tostring(read_watch(w)) end
  tracef:write(table.concat(row, ","), "\n")

  if framesf and frame >= cap_start and (frame - cap_start) % cap_every == 0 then capture_frame() end
  if wramf and frame % wram_every == 0 then dump_wram() end

  for _, pk in ipairs(pokes) do
    if pk.frame == frame then
      if pk.size == 2 then emu.write16(pk.offset, pk.value, pk.mem) else emu.write(pk.offset, pk.value, pk.mem) end
      log(string.format("poke mem=%d off=%d val=%d", pk.mem, pk.offset, pk.value))
    end
  end

  for _, s in ipairs(save_at) do
    if s.frame == frame then
      save_queue[#save_queue + 1] = s.path
      exec_hook_on()
    end
  end

  frame = frame + 1
  if frame >= job.frames then
    if job.save_end then
      save_queue[#save_queue + 1] = job.save_end
      exec_hook_on()
      phase = "saving_end"
    elseif #save_queue > 0 then
      phase = "saving_end"
    else
      finish("ok")
    end
    return
  end
  exec_hook_off()
end

emu.addEventCallback(guarded(on_input_polled), emu.eventType.inputPolled)
emu.addEventCallback(guarded(on_end_frame), emu.eventType.endFrame)

if phase == "loading" then
  exec_hook_on()
  log("carregando savestate " .. job.state)
else
  start_running()
end
