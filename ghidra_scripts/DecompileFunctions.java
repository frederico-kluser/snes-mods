// Descompila as funções que contêm os endereços dados e grava decompile.jsonl.
// Uso headless (projeto já analisado): -process <rom> -noanalysis -readOnly
//   -postScript DecompileFunctions.java <dir-de-saída> <endereço-hex> [<endereço-hex> ...]
//@category snesfab

import java.io.File;
import java.io.FileOutputStream;
import java.io.OutputStreamWriter;
import java.io.PrintWriter;
import java.nio.charset.StandardCharsets;

import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;

public class DecompileFunctions extends GhidraScript {

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

    @Override
    protected void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length < 2) {
            printerr("uso: DecompileFunctions.java <dir-de-saída> <endereço-hex>...");
            return;
        }
        File out = new File(args[0]);
        out.mkdirs();
        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);
        try (PrintWriter w = new PrintWriter(new OutputStreamWriter(new FileOutputStream(new File(out, "decompile.jsonl"), true), StandardCharsets.UTF_8))) {
            for (int i = 1; i < args.length; i++) {
                String req = args[i];
                Address a = currentProgram.getAddressFactory().getDefaultAddressSpace().getAddress(Long.parseLong(req, 16));
                Function f = getFunctionContaining(a);
                if (f == null) {
                    w.println("{\"request\": " + q(req) + ", \"error\": \"sem função no endereço\"}");
                    continue;
                }
                DecompileResults r = ifc.decompileFunction(f, 120, monitor);
                String c = (r != null && r.decompileCompleted() && r.getDecompiledFunction() != null) ? r.getDecompiledFunction().getC() : null;
                String err = r == null ? "sem resultado" : r.getErrorMessage();
                w.println("{\"request\": " + q(req) + ", \"entry\": " + q(String.format("%06X", f.getEntryPoint().getOffset()))
                    + ", \"name\": " + q(f.getName()) + ", \"c\": " + q(c) + ", \"error\": " + q(c == null ? err : null) + "}");
            }
        } finally {
            ifc.dispose();
        }
        println("snesfab: decompilação concluída");
    }
}
