// Exporta a análise do Ghidra (ROM de SNES importada com o loader ghidra-snes) para arquivos
// planos que o snesfab consulta sem reabrir o Ghidra: meta.json, functions.tsv, listing.tsv,
// refs.tsv e symbols.tsv. Uso headless: -postScript ExportSnesEvidence.java <dir-de-saída>
//@category snesfab

import java.io.File;
import java.io.FileOutputStream;
import java.io.OutputStreamWriter;
import java.io.PrintWriter;
import java.math.BigInteger;
import java.nio.charset.StandardCharsets;

import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.address.AddressRange;
import ghidra.program.model.lang.Register;
import ghidra.program.model.lang.RegisterValue;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.FunctionIterator;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.listing.InstructionIterator;
import ghidra.program.model.listing.Listing;
import ghidra.program.model.listing.ProgramContext;
import ghidra.program.model.mem.MemoryBlock;
import ghidra.program.model.symbol.Reference;
import ghidra.program.model.symbol.ReferenceIterator;
import ghidra.program.model.symbol.Symbol;
import ghidra.program.model.symbol.SymbolIterator;

public class ExportSnesEvidence extends GhidraScript {

    private static String q(String s) {
        if (s == null) {
            return "null";
        }
        StringBuilder b = new StringBuilder("\"");
        for (char c : s.toCharArray()) {
            switch (c) {
                case '"': b.append("\\\""); break;
                case '\\': b.append("\\\\"); break;
                case '\n': b.append("\\n"); break;
                case '\r': b.append("\\r"); break;
                case '\t': b.append("\\t"); break;
                default:
                    if (c < 0x20) {
                        b.append(String.format("\\u%04x", (int) c));
                    } else {
                        b.append(c);
                    }
            }
        }
        return b.append('"').toString();
    }

    private static String tsv(String s) {
        return s == null ? "" : s.replace('\t', ' ').replace('\n', ' ').replace('\r', ' ');
    }

    private static String hex(Address a) {
        return String.format("%06X", a.getOffset());
    }

    private PrintWriter open(File dir, String name) throws Exception {
        return new PrintWriter(new OutputStreamWriter(new FileOutputStream(new File(dir, name)), StandardCharsets.UTF_8));
    }

    private String ctx(ProgramContext pc, Register r, Address a) {
        if (r == null) {
            return "";
        }
        RegisterValue v = pc.getRegisterValue(r, a);
        if (v == null || !v.hasValue()) {
            return "";
        }
        BigInteger b = v.getUnsignedValue();
        return b == null ? "" : b.toString();
    }

    @Override
    protected void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length < 1) {
            printerr("uso: ExportSnesEvidence.java <dir-de-saída>");
            return;
        }
        File out = new File(args[0]);
        out.mkdirs();
        Listing listing = currentProgram.getListing();
        ProgramContext pctx = currentProgram.getProgramContext();
        Register mf = currentProgram.getRegister("ctx_MF");
        Register xf = currentProgram.getRegister("ctx_XF");
        Register ef = currentProgram.getRegister("ctx_EF");

        try (PrintWriter w = open(out, "meta.json")) {
            w.println("{");
            w.println("  \"program\": " + q(currentProgram.getName()) + ",");
            w.println("  \"language\": " + q(currentProgram.getLanguageID().getIdAsString()) + ",");
            w.println("  \"compiler\": " + q(currentProgram.getCompilerSpec().getCompilerSpecID().getIdAsString()) + ",");
            w.println("  \"format\": " + q(currentProgram.getExecutableFormat()) + ",");
            w.println("  \"ghidra\": " + q(getGhidraVersion()) + ",");
            w.println("  \"sha256\": " + q(currentProgram.getExecutableSHA256()) + ",");
            w.println("  \"function_count\": " + currentProgram.getFunctionManager().getFunctionCount() + ",");
            w.println("  \"context_registers\": [" + q(mf == null ? null : "ctx_MF") + ", " + q(xf == null ? null : "ctx_XF") + "],");
            w.println("  \"blocks\": [");
            MemoryBlock[] blocks = currentProgram.getMemory().getBlocks();
            for (int i = 0; i < blocks.length; i++) {
                MemoryBlock b = blocks[i];
                w.print("    {\"name\": " + q(b.getName()) + ", \"start\": " + q(hex(b.getStart())) + ", \"end\": " + q(hex(b.getEnd()))
                    + ", \"size\": " + b.getSize() + ", \"initialized\": " + b.isInitialized() + ", \"mapped\": " + b.isMapped()
                    + ", \"type\": " + q(b.getType().toString()) + "}");
                w.println(i < blocks.length - 1 ? "," : "");
            }
            w.println("  ]");
            w.println("}");
        }

        try (PrintWriter w = open(out, "functions.tsv")) {
            w.println("entry\tname\tsize\tranges\tcallers\tcallees\tthunk");
            FunctionIterator it = currentProgram.getFunctionManager().getFunctions(true);
            while (it.hasNext() && !monitor.isCancelled()) {
                Function f = it.next();
                StringBuilder ranges = new StringBuilder();
                for (AddressRange r : f.getBody()) {
                    if (ranges.length() > 0) {
                        ranges.append(',');
                    }
                    ranges.append(hex(r.getMinAddress())).append('-').append(hex(r.getMaxAddress()));
                }
                StringBuilder callers = new StringBuilder();
                for (Function c : f.getCallingFunctions(monitor)) {
                    if (callers.length() > 0) {
                        callers.append(',');
                    }
                    callers.append(hex(c.getEntryPoint()));
                }
                StringBuilder callees = new StringBuilder();
                for (Function c : f.getCalledFunctions(monitor)) {
                    if (callees.length() > 0) {
                        callees.append(',');
                    }
                    callees.append(hex(c.getEntryPoint()));
                }
                w.println(hex(f.getEntryPoint()) + "\t" + tsv(f.getName()) + "\t" + f.getBody().getNumAddresses() + "\t"
                    + ranges + "\t" + callers + "\t" + callees + "\t" + f.isThunk());
            }
        }

        try (PrintWriter w = open(out, "listing.tsv")) {
            w.println("addr\tlen\tbytes\tmnemonic\toperands\tmf\txf\tef\tflow\tfunc");
            InstructionIterator it = listing.getInstructions(true);
            while (it.hasNext() && !monitor.isCancelled()) {
                Instruction ins = it.next();
                Address a = ins.getAddress();
                byte[] bytes = ins.getBytes();
                StringBuilder hb = new StringBuilder();
                for (byte b : bytes) {
                    hb.append(String.format("%02X", b & 0xFF));
                }
                String full = ins.toString();
                String mnem = ins.getMnemonicString();
                String ops = full.length() > mnem.length() ? full.substring(mnem.length()).trim() : "";
                Function f = getFunctionContaining(a);
                w.println(hex(a) + "\t" + ins.getLength() + "\t" + hb + "\t" + tsv(mnem) + "\t" + tsv(ops) + "\t"
                    + ctx(pctx, mf, a) + "\t" + ctx(pctx, xf, a) + "\t" + ctx(pctx, ef, a) + "\t"
                    + ins.getFlowType().toString() + "\t" + (f == null ? "" : hex(f.getEntryPoint())));
            }
        }

        try (PrintWriter w = open(out, "refs.tsv")) {
            w.println("from\tto\ttype\topindex\tprimary");
            ReferenceIterator it = currentProgram.getReferenceManager().getReferenceIterator(currentProgram.getMinAddress());
            while (it.hasNext() && !monitor.isCancelled()) {
                Reference r = it.next();
                if (!r.getToAddress().isMemoryAddress()) {
                    continue;
                }
                w.println(hex(r.getFromAddress()) + "\t" + hex(r.getToAddress()) + "\t" + r.getReferenceType().toString() + "\t"
                    + r.getOperandIndex() + "\t" + r.isPrimary());
            }
        }

        try (PrintWriter w = open(out, "symbols.tsv")) {
            w.println("addr\tname\ttype\tsource");
            SymbolIterator it = currentProgram.getSymbolTable().getAllSymbols(true);
            while (it.hasNext() && !monitor.isCancelled()) {
                Symbol s = it.next();
                if (!s.getAddress().isMemoryAddress()) {
                    continue;
                }
                w.println(hex(s.getAddress()) + "\t" + tsv(s.getName(true)) + "\t" + s.getSymbolType().toString() + "\t" + s.getSource().toString());
            }
        }
        println("snesfab: export concluído em " + out.getAbsolutePath());
    }
}
