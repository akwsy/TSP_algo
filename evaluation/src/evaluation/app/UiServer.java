package evaluation.app;

import algorithms.*;
import app.ScenarioFiles;
import app.GenerationOptions;
import graph.*;
import com.sun.net.httpserver.*;
import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.Executors;

/** Loopback-only, dependency-free HTML UI backed by the actual Java solvers. */
public final class UiServer {
    public static final int MAX_UI_DESTINATIONS = 200;
    private static final int MAX_BODY = 1_000_000;
    private UiServer() {}
    public static void main(String[] args) throws Exception {
        int port = 8765; Path data = Path.of("data"), web = Path.of("../evaluation/web");
        for (int i = 0; i < args.length; i += 2) {
            if (i + 1 == args.length) throw new IllegalArgumentException("Missing option value");
            switch (args[i]) {
                case "--port" -> port = Integer.parseInt(args[i + 1]);
                case "--data" -> data = Path.of(args[i + 1]);
                case "--web" -> web = Path.of(args[i + 1]);
                default -> throw new IllegalArgumentException("Use --port <number> or --data <directory>");
            }
        }
        HttpServer server = start(port, data, web, Path.of("inputs/MY.txt"));
        Runtime.getRuntime().addShutdownHook(new Thread(() -> server.stop(0)));
        System.out.println("Route comparison UI: http://127.0.0.1:" + server.getAddress().getPort());
        System.out.println("Press Ctrl+C to stop. All algorithms run locally in Java.");
    }
    public static HttpServer start(int port, Path data, Path web, Path source) throws IOException {
        if (port < 0 || port > 65535) throw new IllegalArgumentException("Invalid port");
        HttpServer server = HttpServer.create(new InetSocketAddress("127.0.0.1", port), 0);
        Object lock = new Object();
        server.setExecutor(Executors.newCachedThreadPool(task -> {
            Thread thread = new Thread(task, "route-ui"); thread.setDaemon(true); return thread;
        }));
        server.createContext("/", exchange -> {
            try (exchange) {
                String path = exchange.getRequestURI().getPath();
                String expectedHost = "127.0.0.1:" + server.getAddress().getPort();
                String alternateHost = "localhost:" + server.getAddress().getPort();
                String host = exchange.getRequestHeaders().getFirst("Host");
                if (!Set.of(expectedHost, alternateHost).contains(host == null ? "" : host)) {
                    json(exchange, 403, Map.of("error", "Use the local UI address printed by the server")); return;
                }
                if (path.startsWith("/api/")) {
                    String origin = exchange.getRequestHeaders().getFirst("Origin");
                    if (origin != null && !Set.of("http://" + expectedHost, "http://" + alternateHost).contains(origin)) {
                        json(exchange, 403, Map.of("error", "This API accepts requests from the local UI only")); return;
                    }
                    synchronized (lock) { api(exchange, data, source); }
                } else staticFile(exchange, web);
            } catch (Exception failure) {
                // Exchange handling below catches request errors before sending a response.
                System.err.println("UI request ended: " + failure.getMessage());
            }
        });
        server.start(); return server;
    }
    private static void api(HttpExchange request, Path data, Path source) throws IOException {
        try {
            String path = request.getRequestURI().getPath(), method = request.getRequestMethod();
            if (path.equals("/api/scenario") && method.equals("GET")) {
                json(request, 200, ComparisonService.scenario(loadScenario(data, null))); return;
            }
            if (!Set.of("/api/compare", "/api/generate").contains(path)) {
                json(request, 404, Map.of("error", "Unknown API endpoint")); return;
            }
            if (!method.equals("POST")) {
                json(request, 405, Map.of("error", "Use POST for comparisons and generation")); return;
            }
            String type = request.getRequestHeaders().getFirst("Content-Type");
            if (type == null || !type.startsWith("application/x-www-form-urlencoded")) {
                json(request, 415, Map.of("error", "Expected a URL-encoded form")); return;
            }
            byte[] bytes = request.getRequestBody().readNBytes(MAX_BODY + 1);
            if (bytes.length > MAX_BODY) { json(request, 413, Map.of("error", "Input form is too large")); return; }
            Map<String, String> values = form(new String(bytes, StandardCharsets.UTF_8));
            if (path.equals("/api/generate")) {
                int count = integer(values, "count", 10);
                if (count < 1 || count > MAX_UI_DESTINATIONS)
                    throw new IllegalArgumentException("The UI supports 1–200 destinations including depot; use the CLI for larger selections");
                var selection = new GeoNamesLoader.Selection(count, values.getOrDefault("featureClass", "P"),
                        values.getOrDefault("admin1", "14"), Long.parseLong(values.getOrDefault("depot", "1735161")),
                        values.getOrDefault("selection", "population"), Long.parseLong(values.getOrDefault("seed", "42")));
                var options = new GenerationOptions(selection, number(values, "speedKmh", 40),
                        values.getOrDefault("startClock", "08:00"), number(values, "durationMinutes", 120),
                        number(values, "windowSlackMinutes", 30));
                ScenarioFiles.generate(source, data, options);
                json(request, 200, ComparisonService.scenario(loadScenario(data, null))); return;
            }
            Double speed = values.containsKey("speedKmh") ? number(values, "speedKmh", 40) : null;
            var scenario = loadScenario(data, speed);
            if (values.containsKey("windows")) scenario = withWindows(scenario, values.get("windows"));
            double start = number(values, "startTime", 0), duration = number(values, "durationMinutes", scenario.durationMinutes());
            int cap = integer(values, "maxDestinations", 15), milliseconds = integer(values, "timeLimitMs", 1000);
            if (cap < 1 || cap > 20 || milliseconds < 0 || milliseconds > 10000)
                throw new IllegalArgumentException("UI limits: exact cap 1–20, computation budget 0–10000 ms per algorithm");
            json(request, 200, ComparisonService.compare(scenario, start, duration, new SolverOptions(cap, milliseconds)));
        } catch (IllegalArgumentException | IOException failure) {
            json(request, 400, Map.of("error", failure.getMessage() == null ? "Invalid request" : failure.getMessage()));
        } catch (Exception failure) {
            System.err.println("Comparison error: " + failure.getMessage());
            json(request, 500, Map.of("error", "Comparison failed; check the server terminal"));
        }
    }
    private static ScenarioFiles.Scenario loadScenario(Path data, Double speed) throws IOException {
        try (var lines = Files.lines(data.resolve("windows.tsv"), StandardCharsets.UTF_8)) {
            if (lines.filter(line -> !line.isBlank()).limit(MAX_UI_DESTINATIONS + 2L).count() > MAX_UI_DESTINATIONS + 1L)
                throw new IllegalArgumentException("Current scenario exceeds 200 destinations; regenerate a smaller scenario for the UI or use the CLI");
        }
        return ScenarioFiles.load(data, speed);
    }
    private static ScenarioFiles.Scenario withWindows(ScenarioFiles.Scenario scenario, String text) {
        String[] lines = text.split("\\R");
        if (lines.length != scenario.graph().size() + 1 || !lines[0].equals("geonameid\topensAt\tclosesAt"))
            throw new IllegalArgumentException("Provide exactly one window for every current destination");
        Map<Long, double[]> windows = new HashMap<>();
        for (int i = 1; i < lines.length; i++) {
            String[] fields = lines[i].split("\t", -1);
            if (fields.length != 3) throw new IllegalArgumentException("Each window needs ID, opening and closing");
            long id = Long.parseLong(fields[0]); scenario.graph().indexOf(id);
            if (windows.put(id, new double[]{Double.parseDouble(fields[1]), Double.parseDouble(fields[2])}) != null)
                throw new IllegalArgumentException("Duplicate window ID");
        }
        List<Destination> destinations = new ArrayList<>();
        for (var d : scenario.graph().destinations()) {
            double[] w = windows.get(d.geoNameId());
            if (w == null) throw new IllegalArgumentException("Missing customer window");
            destinations.add(new Destination(d.geoNameId(), d.name(), d.latitude(), d.longitude(), w[0], w[1]));
        }
        return new ScenarioFiles.Scenario(new DestinationGraph(destinations, scenario.speedKmh()),
                scenario.clockStartMinutes(), scenario.speedKmh(), scenario.durationMinutes());
    }
    private static Map<String, String> form(String body) {
        Map<String, String> values = new LinkedHashMap<>();
        if (body.isEmpty()) return values;
        for (String entry : body.split("&")) {
            String[] pair = entry.split("=", 2);
            String key = URLDecoder.decode(pair[0], StandardCharsets.UTF_8);
            String value = pair.length == 1 ? "" : URLDecoder.decode(pair[1], StandardCharsets.UTF_8);
            if (values.put(key, value) != null) throw new IllegalArgumentException("Duplicate form field");
        }
        return values;
    }
    private static double number(Map<String, String> values, String key, double fallback) {
        double value = Double.parseDouble(values.getOrDefault(key, Double.toString(fallback)));
        if (!Double.isFinite(value)) throw new IllegalArgumentException(key + " must be finite");
        return value;
    }
    private static int integer(Map<String, String> values, String key, int fallback) {
        return Integer.parseInt(values.getOrDefault(key, Integer.toString(fallback)));
    }
    private static void staticFile(HttpExchange request, Path web) throws IOException {
        if (!request.getRequestMethod().equals("GET")) { json(request, 405, Map.of("error", "Use GET")); return; }
        String file = switch (request.getRequestURI().getPath()) {
            case "/", "/index.html" -> "index.html";
            case "/app.js" -> "app.js";
            case "/inspection.js" -> "inspection.js";
            case "/styles.css" -> "styles.css";
            default -> null;
        };
        if (file == null) { json(request, 404, Map.of("error", "Not found")); return; }
        String type = file.endsWith(".js") ? "text/javascript" : file.endsWith(".css") ? "text/css" : "text/html";
        send(request, 200, type + "; charset=utf-8", Files.readAllBytes(web.resolve(file)));
    }
    private static void json(HttpExchange request, int status, Object value) throws IOException {
        send(request, status, "application/json; charset=utf-8", Json.stringify(value).getBytes(StandardCharsets.UTF_8));
    }
    private static void send(HttpExchange request, int status, String type, byte[] bytes) throws IOException {
        request.getResponseHeaders().set("Content-Type", type);
        request.getResponseHeaders().set("Cache-Control", "no-store");
        request.getResponseHeaders().set("X-Content-Type-Options", "nosniff");
        request.getResponseHeaders().set("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'");
        request.sendResponseHeaders(status, bytes.length);
        request.getResponseBody().write(bytes);
    }
}
