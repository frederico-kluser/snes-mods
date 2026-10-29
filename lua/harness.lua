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
local guarded  -- definido abaixo (embrulha callbacks: erro vira finish("error"))

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
local warmup = job.warmup or 0  -- frames iniciais emulados SEM medir (o state traz RAM/CGRAM velhas da ROM limpa)
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
local cap_set = {}          -- frames avulsos a capturar além do "a cada N"
for _, f in ipairs(cap.frames or {}) do cap_set[f] = true end
local framesf, idxf, frames_offset, frames_captured = nil, nil, 0, 0
if cap_every > 0 or next(cap_set) then
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
local wram_set = {}         -- frames avulsos com dump da WRAM
for _, f in ipairs(job.wram_frames or {}) do wram_set[f] = true end
local wramf, wram_dumps = nil, 0
local wramidx = nil
if wram_every > 0 or next(wram_set) then
  wramf = io.open(OUT .. "/wram.bin", "wb")
  wramidx = io.open(OUT .. "/wram_index.csv", "w")      -- frame de cada dump, na ordem do arquivo
  wramidx:write("frame\n")
end

-- snapshots do PPU (OAM 544 + CGRAM 512 + VRAM 65536 bytes por frame) para renderizar sprites fora do
-- emulador, e "falsa cor" (CGRAM trocada por cores-código durante o frame: a imagem diz o ÍNDICE de cada píxel)
local ppu_set, fc_set = {}, {}
for _, f in ipairs(job.ppu_frames or {}) do ppu_set[f] = true end
for _, f in ipairs(job.false_color or {}) do fc_set[f] = true end
local ppu_every = job.ppu_every or 0
local ppuf, ppuidx, ppu_dumps = nil, nil, 0
if next(ppu_set) or ppu_every > 0 then
  ppuf = io.open(OUT .. "/ppu.bin", "wb")
  ppuidx = io.open(OUT .. "/ppu_index.jsonl", "w")
end
local fc_colors = job.false_color_values or {}

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

-- ── PPU: snapshot e falsa cor ───────────────────────────────────────────────
local PPU_KEYS = { "scanline", "forcedBlank", "screenBrightness", "oamMode", "oamBaseAddress", "oamAddressOffset",
  "enableOamPriority", "internalOamAddress", "bgMode", "mainScreenLayers", "subScreenLayers", "colorMathEnabled",
  "objInterlace", "overscanMode" }
for i = 0, 3 do   -- camadas de BG: onde ficam o mapa (tilemap) e os tiles (chr), em palavras da VRAM
  for _, f in ipairs({ "tilemapAddress", "chrAddress", "doubleWidth", "doubleHeight", "largeTiles" }) do
    PPU_KEYS[#PPU_KEYS + 1] = "layers[" .. i .. "]." .. f
  end
end

local function ppu_wanted(f)
  return f >= warmup and (ppu_set[f] or (ppu_every > 0 and f % ppu_every == 0))
end

local fc_saved = nil       -- CGRAM real (256 palavras) guardada enquanto a falsa cor está na tela
local ppu_pending = false  -- snapshot deste frame ainda por fazer (à espera do display ligado)

local function read_block(mt, size, t)
  local out = {}
  for base = 0, size - 1, 256 do
    local n = math.min(256, size - base)
    for i = 0, n - 1 do t[i + 1] = emu.read(base + i, mt, false) end
    out[#out + 1] = string.char(table.unpack(t, 1, n))
  end
  return table.concat(out)
end

local function ppu_snapshot(event, st)
  local t = {}
  local oam = read_block(emu.memType.snesSpriteRam, 0x220, t)
  local cg
  if fc_saved then              -- frame em falsa cor: o snapshot leva a CGRAM REAL guardada
    local p = {}
    for i = 0, 255 do p[#p + 1] = string.char(fc_saved[i] & 0xFF, (fc_saved[i] >> 8) & 0xFF) end
    cg = table.concat(p)
  else
    cg = read_block(emu.memType.snesCgRam, 0x200, t)
  end
  local vram = read_block(emu.memType.snesVideoRam, 0x10000, t)
  ppuf:write(oam, cg, vram)
  local parts = { string.format('"frame":%d,"event":"%s"', frame, event) }
  for _, k in ipairs(PPU_KEYS) do
    local v = st["ppu." .. k]
    if type(v) == "boolean" then v = tostring(v) elseif v == nil then v = "null" else v = tostring(v) end
    parts[#parts + 1] = string.format('"%s":%s', k, v)
  end
  ppuidx:write("{", table.concat(parts, ","), "}\n")
  ppu_dumps = ppu_dumps + 1
  ppu_pending = false
end

local function fc_write()
  for i = 0, 255 do emu.write16(i * 2, fc_colors[i + 1], emu.memType.snesCgRam) end
end

local function fc_restore()
  -- devolve só as entradas que o jogo não reescreveu (DMA de paleta no fim do frame é do frame seguinte)
  for i = 0, 255 do
    if emu.read16(i * 2, emu.memType.snesCgRam) == fc_colors[i + 1] then
      emu.write16(i * 2, fc_saved[i], emu.memType.snesCgRam)
    end
  end
  fc_saved = nil
end

-- ── log de DMA/HDMA: cada escrita em MDMAEN ($420B) ou HDMAEN ($420C), por QUALQUER banco-espelho
-- ($00-$3F/$80-$BF: o SFA2 escreve por $BF:420B porque roda com DBR=$BF) → de onde vêm paleta, OAM e
-- gráficos, e que instrução dispara a transferência (ponto de hook) ──
local dmaf, dma_count = nil, 0
if job.dma_log then dmaf = io.open(OUT .. "/dma.jsonl", "w") end

-- uploads de gráfico: o que cada DMA para a VRAM DEIXOU lá (já descomprimido, qualquer que seja o formato
-- na ROM). Os bytes são lidos da VRAM quando a transferência já terminou: no próximo $420B (o DMA anterior
-- acabou) ou no início/fim do frame. Base do "export completo do tileset" de qualquer jogo.
local upf, upidx, up_count, up_bytes = nil, nil, 0, 0
if job.vram_uploads then
  upf = io.open(OUT .. "/vram_uploads.bin", "wb")
  upidx = io.open(OUT .. "/vram_uploads.jsonl", "w")
end
local up_pending, up_offset = {}, 0

local function flush_uploads()
  if not upf or #up_pending == 0 then return end
  local t = {}
  for _, u in ipairs(up_pending) do
    local parts = {}
    for base = 0, u.size - 1, 256 do
      local m = math.min(256, u.size - base)
      for i = 0, m - 1 do t[i + 1] = emu.read((u.start + base + i) & 0xFFFF, emu.memType.snesVideoRam, false) end
      parts[#parts + 1] = string.char(table.unpack(t, 1, m))
    end
    upf:write(table.concat(parts))
    upidx:write(string.format(
      '{"frame":%d,"dma":%d,"ch":%d,"start":%d,"size":%d,"offset":%d,"src":%d,"bbad":%d,"mode":%d,"linear":%s,"k":%d,"pc":%d,"ps":%d}\n',
      u.frame, u.dma, u.ch, u.start, u.size, up_offset, u.src, u.bbad, u.mode, tostring(u.linear), u.k, u.pc, u.ps))
    up_offset = up_offset + u.size
    up_bytes = up_bytes + u.size
    up_count = up_count + 1
  end
  up_pending = {}
end

local function dma_cb(kind)
  -- os registradores $43xx vêm do estado do controlador de DMA (getState), não de emu.read: chips como o
  -- S-DD1 interceptam $43xx e a leitura de depuração devolve 0
  return function(address, value)
    if phase ~= "running" or frame < warmup or value == 0 then return end
    if kind == "dma" then flush_uploads() end      -- os DMAs anteriores já terminaram
    local st = emu.getState()
    local c = emu.getCpuState(CPU_SNES)
    local chip = st["cart.coprocessor.allowDmaProcessing"]
    local vram_next = ((st["ppu.vramAddress"] or 0) * 2) & 0xFFFF
    for ch = 0, 7 do
      if (value >> ch) & 1 == 1 then
        local p = "dmaController.channel[" .. ch .. "]."
        local mode = (st[p .. "transferMode"] or 0) | ((st[p .. "invertDirection"] and 1 or 0) << 7)
          | ((st[p .. "fixedTransfer"] and 1 or 0) << 3) | ((st[p .. "decrement"] and 1 or 0) << 4)
          | ((st[p .. "hdmaIndirectAddressing"] and 1 or 0) << 6) | ((st[p .. "unusedFlag"] and 1 or 0) << 5)
        local bbad = st[p .. "destAddress"] or 0
        if upf and kind == "dma" and (bbad == 0x18 or bbad == 0x19) and not st[p .. "invertDirection"] then
          local size = st[p .. "transferSize"] or 0
          if size == 0 then size = 0x10000 end
          local linear = bbad == 0x18 and (st[p .. "transferMode"] or 0) == 1 and st["ppu.vramIncrementValue"] == 1
            and st["ppu.vramAddrIncrementOnSecondReg"] == true and (st["ppu.vramAddressRemapping"] or 0) == 0
          up_pending[#up_pending + 1] = { frame = frame, dma = dma_count, ch = ch, start = vram_next, size = size,
            bbad = bbad, src = ((st[p .. "srcBank"] or 0) << 16) | (st[p .. "srcAddress"] or 0), mode = mode,
            linear = linear, k = c.k or 0, pc = c.pc or 0, ps = c.ps or 0 }
          vram_next = (vram_next + size) & 0xFFFF     -- canal seguinte no mesmo $420B continua de onde este parou
        end
        dmaf:write(string.format(
          '{"kind":"%s","frame":%d,"scanline":%s,"ch":%d,"dmap":%d,"bbad":%d,"src":%d,"size":%d,"vram":%s,"cgram":%s,"oam":%s,"fb":%s,"chip_dma":%s,"k":%d,"pc":%d,"ps":%d,"dbr":%d}\n',
          kind, frame, tostring(st["ppu.scanline"]), ch, mode, st[p .. "destAddress"] or 0,
          ((st[p .. "srcBank"] or 0) << 16) | (st[p .. "srcAddress"] or 0), st[p .. "transferSize"] or 0,
          tostring(st["ppu.vramAddress"]), tostring(st["ppu.cgramAddress"]), tostring(st["ppu.internalOamAddress"]),
          tostring(st["ppu.forcedBlank"]), chip == nil and "null" or tostring(chip), c.k or 0, c.pc or 0, c.ps or 0,
          c.dbr or 0))
        dma_count = dma_count + 1
      end
    end
  end
end

local function register_dma_log()
  if not dmaf then return end
  local cb_dma, cb_hdma = dma_cb("dma"), dma_cb("hdma")
  for _, bank in ipairs({ 0x00, 0x80 }) do
    for i = 0, 0x3F do
      local a = ((bank + i) << 16)
      emu.addMemoryCallback(guarded(cb_dma), emu.callbackType.write, a | 0x420B, a | 0x420B, CPU_SNES, MT_CPU)
      emu.addMemoryCallback(guarded(cb_hdma), emu.callbackType.write, a | 0x420C, a | 0x420C, CPU_SNES, MT_CPU)
    end
  end
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
  if wramidx then wramidx:close() end
  if ppuf then ppuf:close(); ppuidx:close() end
  if dmaf then dmaf:close() end
  if upf then flush_uploads(); upf:close(); upidx:close() end
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
  r:write('  "warmup": ', warmup, ',\n')
  r:write('  "frames_measured": ', math.max(0, frame - warmup), ',\n')
  r:write('  "state": ', job.state and json_str(job.state) or "null", ',\n')
  r:write('  "state_loaded": ', tostring(state_ok == true), ',\n')
  r:write('  "frames_captured": ', frames_captured, ',\n')
  r:write('  "wram_dumps": ', wram_dumps, ',\n')
  r:write('  "ppu_dumps": ', ppu_dumps, ',\n')
  r:write('  "dma_events": ', dma_count, ',\n')
  r:write('  "vram_uploads": ', up_count, ',\n')
  r:write('  "vram_upload_bytes": ', up_bytes, ',\n')
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
  register_dma_log()
  log("cenário iniciado" .. (job.state and (" (state ok=" .. tostring(state_ok) .. ")") or " (power-on)"))
end

-- início do frame (linha 0): a falsa cor entra aqui (depois do DMA de paleta do VBlank) e o snapshot do
-- PPU é feito com o display LIGADO — jogos que esticam o VBlank com forced blank (SFA2: display só nas
-- linhas ~24-215, DMA fora disso) esperam pelo 1.º IRQ/NMI com o display ligado; se não houver, endFrame
local display_seen = false  -- o display já esteve ligado neste frame (daí em diante o PPU está a desenhar)

local function on_start_frame()
  if phase ~= "running" then return end
  flush_uploads()
  local st = emu.getState()
  display_seen = st["ppu.forcedBlank"] == false
  if fc_set[frame] and frame >= warmup then
    fc_saved = {}
    for i = 0, 255 do fc_saved[i] = emu.read16(i * 2, emu.memType.snesCgRam) end
    fc_write()
  end
  if ppu_wanted(frame) then
    if display_seen then ppu_snapshot("start", st) else ppu_pending = true end
  end
end

local function on_irq_or_nmi()
  if phase ~= "running" or display_seen then return end
  if not (ppu_pending or fc_saved) then return end
  local st = emu.getState()
  if st["ppu.forcedBlank"] then
    if fc_saved then fc_write() end      -- DMA de paleta ainda no forced blank do topo: repõe a falsa cor
  else
    display_seen = true
    if ppu_pending then ppu_snapshot("irq@" .. tostring(st["ppu.scanline"]), st) end
  end
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
  flush_uploads()
  if frame >= warmup then
    local row = { tostring(frame), tostring(cur_mask) }
    for _, w in ipairs(watches) do row[#row + 1] = tostring(read_watch(w)) end
    tracef:write(table.concat(row, ","), "\n")

    if framesf and ((cap_every > 0 and frame >= cap_start and (frame - cap_start) % cap_every == 0) or cap_set[frame]) then
      capture_frame()
    end
    if wramf and ((wram_every > 0 and frame % wram_every == 0) or wram_set[frame]) then
      dump_wram()
      if wramidx then wramidx:write(frame, "\n") end
    end
    if ppu_pending then ppu_snapshot("end", emu.getState()) end
  end
  if fc_saved then fc_restore() end

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
if ppuf or next(fc_set) or upf then
  emu.addEventCallback(guarded(on_start_frame), emu.eventType.startFrame)
  emu.addEventCallback(guarded(on_irq_or_nmi), emu.eventType.irq)
  emu.addEventCallback(guarded(on_irq_or_nmi), emu.eventType.nmi)
end

if phase == "loading" then
  exec_hook_on()
  log("carregando savestate " .. job.state)
else
  start_running()
end
