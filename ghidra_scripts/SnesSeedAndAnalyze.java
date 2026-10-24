// Semeia a desmontagem de uma ROM de SNES com o contexto M/X/E correto e roda a auto-análise.
// O loader ghidra-snes mapeia a ROM mas não segue os vetores (a tabela de vetores acabava
// desmontada como código). Aqui: limpa a tabela de vetores ($00:FFE0-$FFFF) e cria words,
// e para cada semente (endereço canônico + M/X/E) define o contexto, desmonta e cria função.
// As sementes vêm do snesfab: vetores do cabeçalho + CDL do MesenCE (M/X observados em execução).
// Uso headless: -postScript SnesSeedAndAnalyze.java <seeds.tsv>
//   seeds.tsv: addr(hex 24 bits) \t m(1=8 bits) \t x(1=8 bits) \t e(1=emulação) \t nome
//@category snesfab

import java.io.BufferedReader;
import java.io.File;
import java.io.FileInputStream;
import java.io.InputStreamReader;
import java.math.BigInteger;
import java.nio.charset.StandardCharsets;

import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.lang.Register;
import ghidra.program.model.listing.ProgramContext;
import ghidra.program.model.mem.MemoryBlock;
import ghidra.program.model.symbol.SourceType;

public class SnesSeedAndAnalyze extends GhidraScript {

    private void setCtx(ProgramContext pc, Register r, Address a, int v) {
        if (r == null || v < 0) {
            return;
        }
        try {
            pc.setValue(r, a, a, BigInteger.valueOf(v));
        } catch (Exception e) {
            printerr("contexto " + r.getName() + " em " + a + ": " + e.getMessage());
        }
    }

    @Override
    protected void run() throws Exception {
        String[] args = getScriptArgs();
        ProgramContext pctx = currentProgram.getProgramContext();
        Register mf = currentProgram.getRegister("ctx_MF");
        Register xf = currentProgram.getRegister("ctx_XF");
        Register ef = currentProgram.getRegister("ctx_EF");

        // 1. tabela de vetores como dados (words), nos blocos onde existir
        for (long base : new long[] { 0x00FFE0L, 0x80FFE0L, 0xC0FFE0L }) {
            Address s = toAddr(base);
            MemoryBlock b = getMemoryBlock(s);
            if (b == null) {
                continue;
            }
            clearListing(s, toAddr(base + 0x1F));
            for (int i = 0; i < 0x20; i += 2) {
                try {
                    createWord(toAddr(base + i));
                } catch (Exception e) {
                    // ignora palavras já definidas
                }
            }
        }

        // 2. sementes
        int seeded = 0, failed = 0;
        if (args.length >= 1 && !args[0].equals("-")) {
            File f = new File(args[0]);
            try (BufferedReader r = new BufferedReader(new InputStreamReader(new FileInputStream(f), StandardCharsets.UTF_8))) {
                String line;
                while ((line = r.readLine()) != null) {
                    line = line.trim();
                    if (line.isEmpty() || line.startsWith("#")) {
                        continue;
                    }
                    String[] p = line.split("\t");
                    Address a = toAddr(Long.parseLong(p[0], 16));
                    if (getMemoryBlock(a) == null || !getMemoryBlock(a).isInitialized() && !getMemoryBlock(a).isMapped()) {
                        failed++;
                        continue;
                    }
                    int m = Integer.parseInt(p[1]);
                    int x = Integer.parseInt(p[2]);
                    int e = Integer.parseInt(p[3]);
                    String name = p.length > 4 ? p[4] : null;
                    if (getInstructionAt(a) == null) {
                        setCtx(pctx, ef, a, e);
                        setCtx(pctx, mf, a, m);
                        setCtx(pctx, xf, a, x);
                        if (!disassemble(a)) {
                            failed++;
                            continue;
                        }
                    }
                    if (getFunctionAt(a) == null) {
                        try {
                            createFunction(a, name);
                        } catch (Exception ex) {
                            // sem função (p.ex. alvo no meio de outra): fica a desmontagem
                        }
                    } else if (name != null && getFunctionAt(a).getName().startsWith("FUN_")) {
                        getFunctionAt(a).setName(name, SourceType.ANALYSIS);
                    }
                    seeded++;
                }
            }
        }
        println("snesfab: sementes aplicadas=" + seeded + " falhadas=" + failed);

        // 3. auto-análise com o contexto semeado
        analyzeAll(currentProgram);
        println("snesfab: análise concluída; funções=" + currentProgram.getFunctionManager().getFunctionCount());
    }
}
