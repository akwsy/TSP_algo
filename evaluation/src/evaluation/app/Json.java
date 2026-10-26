package evaluation.app;

import java.util.*;

/** Small JSON writer for API output; no external dependencies or reflection. */
public final class Json {
    private Json() {}
    public static String stringify(Object value) {
        StringBuilder text = new StringBuilder(); append(text, value); return text.toString();
    }
    private static void append(StringBuilder out, Object value) {
        if (value == null) out.append("null");
        else if (value instanceof String s) {
            out.append('"');
            for (int i = 0; i < s.length(); i++) {
                char c = s.charAt(i);
                switch (c) {
                    case '"' -> out.append("\\\"");
                    case '\\' -> out.append("\\\\");
                    case '\n' -> out.append("\\n");
                    case '\r' -> out.append("\\r");
                    case '\t' -> out.append("\\t");
                    default -> { if (c < 32) out.append(String.format(Locale.ROOT, "\\u%04x", (int)c)); else out.append(c); }
                }
            }
            out.append('"');
        } else if (value instanceof Number n) {
            if (!Double.isFinite(n.doubleValue())) throw new IllegalArgumentException("JSON number must be finite");
            out.append(n);
        } else if (value instanceof Boolean b) out.append(b);
        else if (value instanceof Map<?, ?> map) {
            out.append('{'); boolean first = true;
            for (var entry : map.entrySet()) {
                if (!first) out.append(','); first = false;
                append(out, entry.getKey().toString()); out.append(':'); append(out, entry.getValue());
            }
            out.append('}');
        } else if (value instanceof Iterable<?> values) {
            out.append('['); boolean first = true;
            for (Object item : values) { if (!first) out.append(','); first = false; append(out, item); }
            out.append(']');
        } else throw new IllegalArgumentException("Unsupported JSON value");
    }
}
