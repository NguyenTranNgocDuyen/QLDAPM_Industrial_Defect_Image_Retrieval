package com.industrial.defect;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.industrial.defect.controller.DamageAssetController;
import com.industrial.defect.controller.DetectionController;
import com.industrial.defect.entity.ScanRecord;
import com.industrial.defect.repository.ScanRecordRepository;
import com.industrial.defect.service.PythonDamageClient;
import com.industrial.defect.service.ScanService;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.springframework.mock.web.MockMultipartFile;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import java.net.ServerSocket;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;
import java.util.UUID;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@EnabledIfEnvironmentVariable(named="DAMAGE_REAL_PYTHON", matches=".+")
class RealDamageWorkerSmokeTests {
    @Test void javaMultipartToRealCheckpointsAndPng() throws Exception {
        int port;
        try (var socket = new ServerSocket(0)) { port = socket.getLocalPort(); }
        var root = Path.of("..").toAbsolutePath().normalize();
        var process = new ProcessBuilder(System.getenv("DAMAGE_REAL_PYTHON"), "-m", "defect_vision.damage_api",
                "--port", Integer.toString(port), "--device", "cpu")
                .directory(root.resolve("image-processing").toFile()).redirectErrorStream(true)
                .redirectOutput(Path.of("target", "real-worker.log").toFile()).start();
        try {
            String base = "http://127.0.0.1:" + port;
            var http = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(1)).build();
            boolean ready = false;
            for (int i=0; i<90 && process.isAlive(); i++) {
                try {
                    ready = http.send(HttpRequest.newBuilder(URI.create(base + "/health"))
                            .timeout(Duration.ofSeconds(1)).build(), HttpResponse.BodyHandlers.discarding()).statusCode() == 200;
                    if (ready) break;
                } catch (Exception ignored) { }
                Thread.sleep(500);
            }
            assertTrue(ready, "Real Python worker failed startup; see target/real-worker.log");
            var repository = mock(ScanRecordRepository.class);
            when(repository.save(any())).thenAnswer(call -> {
                ScanRecord scan = call.getArgument(0); scan.setId(UUID.randomUUID()); return scan;
            });
            var mapper = new ObjectMapper();
            var python = new PythonDamageClient(base, 1000, 300000);
            var mvc = MockMvcBuilders.standaloneSetup(
                    new DetectionController(new ScanService(repository, python, mapper)),
                    new DamageAssetController(python)).build();
            byte[] image = Files.readAllBytes(root.resolve("image-processing/data/123k.jpeg"));
            var response = mvc.perform(multipart("/api/detections")
                    .file(new MockMultipartFile("image", "123k.jpeg", "image/jpeg", image)).param("surface", "front"))
                    .andExpect(status().isOk()).andExpect(jsonPath("$.success").value(true))
                    .andExpect(jsonPath("$.damage.threshold").value(0.4))
                    .andExpect(jsonPath("$.damage.detector_loaded_in_damage_engine").value(false))
                    .andExpect(jsonPath("$.severity.estimation_basis").value("image_geometry"))
                    .andExpect(jsonPath("$.severity.estimated_severity").isNotEmpty())
                    .andExpect(jsonPath("$.severity.locations").isNotEmpty())
                    .andExpect(jsonPath("$.severity.needs_review").value(true)).andReturn();
            String result = response.getResponse().getContentAsString();
            Files.writeString(Path.of("target", "real-worker-response.json"), result);
            var parsed = mapper.readTree(result);
            assertTrue(parsed.path("damage").path("candidate_pixels_original").asInt() > 0);
            mvc.perform(get(parsed.path("assets").path("damage_rectified").asText()))
                    .andExpect(status().isOk()).andExpect(content().contentType("image/png"));
            String health = http.send(HttpRequest.newBuilder(URI.create(base + "/health")).build(),
                    HttpResponse.BodyHandlers.ofString()).body();
            assertEquals(1, mapper.readTree(health).path("detector_calls").asInt());
            verify(repository, times(1)).save(any());
        } finally {
            process.destroy();
            if (!process.waitFor(5, java.util.concurrent.TimeUnit.SECONDS)) process.destroyForcibly();
        }
    }
}
