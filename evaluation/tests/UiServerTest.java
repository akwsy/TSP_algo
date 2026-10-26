package tests;

import app.*;
import evaluation.app.*;
import graph.GeoNamesLoader;
import com.sun.net.httpserver.HttpServer;
import java.io.*;
import java.net.*;
import java.net.http.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.time.Duration;
import java.util.*;

/** End-to-end API tests against an ephemeral loopback server and disposable data. */
public final class UiServerTest {
    private static int assertions;
    private static void check(boolean condition, String message) {
        assertions++; if (!condition) throw new AssertionError(message);
    }
    public static void main(String[] args) throws Exception {
        Path tmp = Files.createTempDirectory("route-ui-test-"); HttpServer server = null;
        try {
            Path source = tmp.resolve("MY.txt"), data = tmp.resolve("data");
            StringBuilder rows = new StringBuilder();
            for (int i = 1; i <= 3; i++) {
                String[] row = new String[19]; Arrays.fill(row, "");
                row[0] = Integer.toString(i); row[1] = "Place \"" + i + "\"";
                row[4] = "0"; row[5] = Double.toString((i - 1) * .01);
                row[6] = "P"; row[7] = "PPL"; row[8] = "MY"; row[10] = "14"; row[14] = "100";
                rows.append(String.join("\t", row)).append('\n');
            }
            Files.writeString(source, rows);
            ScenarioFiles.generate(source, data, new GenerationOptions(
                    new GeoNamesLoader.Selection(3, "P", "14", 1, "population", 42), 40, "08:00", 120, 30));
            var current = ScenarioFiles.load(data, null);
            var snapshot = ComparisonService.scenario(current);
            var matrix = (List<?>) snapshot.get("distanceKm");
            check(matrix.size() == 3, "Hover matrix covers every destination");
            check(((List<?>) matrix.get(0)).size() == 3, "Hover matrix covers every origin");
            check(((Number)((List<?>) matrix.get(0)).get(0)).doubleValue() == 0, "Hover distance to itself is zero");
            double hoverDistance = ((Number)((List<?>) matrix.get(0)).get(1)).doubleValue();
            check(hoverDistance == current.graph().distance(0, 1), "Hover distance uses actual Java graph");
            check(hoverDistance == ((Number)((List<?>) matrix.get(1)).get(0)).doubleValue(), "Hover distances are symmetric");
            check(Math.abs(hoverDistance * 60 / current.speedKmh() - current.graph().travelMinutes(0, 1)) < 1e-9,
                    "Hover travel time agrees with Java travel matrix");
            server = UiServer.start(0, data, Path.of("../evaluation/web"), source);
            String base = "http://127.0.0.1:" + server.getAddress().getPort();
            HttpClient client = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(3)).build();
            var html = get(client, base + "/");
            check(html.statusCode() == 200 && html.body().contains("Compare the results"), "HTML served");
            check(html.headers().firstValue("Content-Security-Policy").isPresent(), "Local assets policy");
            check(get(client, base + "/styles.css").statusCode() == 200, "CSS served");
            check(get(client, base + "/inspection.js").statusCode() == 200, "Inspection time/window helpers served");
            check(get(client, base + "/app.js").body().contains("renderResults"), "JS served");
            check(get(client, base + "/inputs/MY.txt").statusCode() == 404, "Source files are not exposed as static assets");
            check(get(client, base + "/api/scenario").body().contains("\"customerCount\":2"), "Current input scenario");
            check(get(client, base + "/api/scenario").body().contains("\"distanceKm\":[["), "Hover distances are exposed in scenario JSON");
            check(get(client, base + "/api/compare").statusCode() == 405, "Compare requires POST");
            var compare = post(client, base + "/api/compare", Map.of("durationMinutes", "120", "speedKmh", "40", "timeLimitMs", "1000"));
            check(compare.statusCode() == 200, "Comparison API succeeds");
            for (String id : List.of("nearest", "greedy", "exact"))
                check(compare.body().contains("\"id\":\"" + id + "\""), "Includes solver " + id);
            check(compare.body().contains("\"status\":\"OPTIMAL\""), "Exact proof status");
            check(compare.body().contains("\"legDistanceKm\"") && compare.body().contains("\"skipped\""), "Detailed route output");
            check(compare.body().contains("Place \\\"1\\\""), "Names are JSON escaped");
            var cap = post(client, base + "/api/compare", Map.of("maxDestinations", "1"));
            check(cap.statusCode() == 200 && cap.body().contains("SEARCH_LIMIT_REACHED"), "Exact cap retained in output");
            var zero = post(client, base + "/api/compare", Map.of("timeLimitMs", "0"));
            check(zero.statusCode() == 200 && occurrences(zero.body(), "SEARCH_LIMIT_REACHED") == 3, "Every solver reports zero budget honestly");
            String originalWindows = Files.readString(data.resolve("windows.tsv"));
            String overrides = "geonameid\topensAt\tclosesAt\n1\t0\t10000\n2\t0\t0\n3\t0\t0";
            var edited = post(client, base + "/api/compare", Map.of("windows", overrides));
            check(edited.statusCode() == 200 && occurrences(edited.body(), "\"visitedCount\":0") == 3, "Edited windows reach all solvers");
            check(Files.readString(data.resolve("windows.tsv")).equals(originalWindows), "Comparison edits are not persisted");
            check(post(client, base + "/api/compare", Map.of("windows", "bad")).statusCode() == 400, "Malformed windows rejected");
            check(post(client, base + "/api/compare", Map.of("durationMinutes", "-1")).statusCode() == 400, "Negative period rejected");
            check(post(client, base + "/api/compare", Map.of("speedKmh", "NaN")).statusCode() == 400, "Nonfinite speed rejected");
            check(post(client, base + "/api/compare", Map.of("timeLimitMs", "10001")).statusCode() == 400, "UI computation guard");
            var foreign = client.send(HttpRequest.newBuilder(URI.create(base + "/api/generate"))
                    .header("Origin", "https://example.invalid").header("Content-Type", "application/x-www-form-urlencoded")
                    .POST(HttpRequest.BodyPublishers.ofString("count=1")).build(), HttpResponse.BodyHandlers.ofString());
            check(foreign.statusCode() == 403, "Foreign origins cannot replace the scenario");
            check(post(client, base + "/api/generate", Map.of("count", "2", "depot", "1", "selection", "random")).statusCode() == 200, "Regenerate from bundled-source contract");
            check(ScenarioFiles.load(data, null).graph().size() == 2, "Generation replaces current data");
            check(Files.readString(source).equals(rows.toString()), "Full source unchanged");
            check(post(client, base + "/api/generate", Map.of("count", "201")).statusCode() == 400, "UI count limit");
            check(ScenarioFiles.load(data, null).graph().size() == 2, "Rejected generation leaves scenario intact");
            check(Json.stringify(Map.of("text", "quote\" slash\\ newline\n tab\t control\u0001")).contains("\\u0001"), "JSON control characters escaped");
            System.out.println("PASS: " + assertions + " UI/API assertions against a temporary local server.");
        } finally {
            if (server != null) server.stop(0);
            try (var paths = Files.walk(tmp)) {
                for (Path path : paths.sorted(Comparator.reverseOrder()).toList()) Files.delete(path);
            }
        }
    }
    private static int occurrences(String text, String part) { return (text.length() - text.replace(part, "").length()) / part.length(); }
    private static HttpResponse<String> get(HttpClient client, String url) throws Exception {
        return client.send(HttpRequest.newBuilder(URI.create(url)).GET().build(), HttpResponse.BodyHandlers.ofString());
    }
    private static HttpResponse<String> post(HttpClient client, String url, Map<String, String> values) throws Exception {
        List<String> fields = new ArrayList<>();
        values.forEach((key, value) -> fields.add(URLEncoder.encode(key, StandardCharsets.UTF_8) + "=" + URLEncoder.encode(value, StandardCharsets.UTF_8)));
        return client.send(HttpRequest.newBuilder(URI.create(url)).header("Content-Type", "application/x-www-form-urlencoded")
                .POST(HttpRequest.BodyPublishers.ofString(String.join("&", fields))).build(), HttpResponse.BodyHandlers.ofString());
    }
}
