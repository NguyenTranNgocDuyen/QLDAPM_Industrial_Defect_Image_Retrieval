package com.industrial.defect;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.industrial.defect.controller.DamageAssetController;
import com.industrial.defect.controller.DetectionController;
import com.industrial.defect.controller.ScanController;
import com.industrial.defect.entity.ScanRecord;
import com.industrial.defect.exception.GlobalExceptionHandler;
import com.industrial.defect.repository.ScanRecordRepository;
import com.industrial.defect.service.PythonDamageClient;
import com.industrial.defect.service.ScanService;
import com.sun.net.httpserver.HttpServer;
import org.junit.jupiter.api.*;
import org.springframework.data.domain.PageImpl;
import org.springframework.data.domain.Pageable;
import org.springframework.mock.web.MockMultipartFile;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import java.util.concurrent.atomic.AtomicReference;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

class DamageApiIntegrationTests {
    private HttpServer worker;
    private MockMvc mvc;
    private ScanRecordRepository repository;
    private final AtomicReference<byte[]> uploaded = new AtomicReference<>();
    private final AtomicReference<String> query = new AtomicReference<>();
    private final AtomicReference<ScanRecord> stored = new AtomicReference<>();
    private final UUID id = UUID.randomUUID();
    private final AtomicReference<String> workerResult = new AtomicReference<>();

    @BeforeEach
    void setUp() throws Exception {
        // Local protocol fixture only; real checkpoints are verified by the Python smoke script.
        workerResult.set("""
          {"scanId":"00000000-0000-0000-0000-000000000001","success":true,"hasDefect":false,
           "status":"needs_review","sourceImage":{"width":200,"height":200,"url":"/api/damage-assets/00000000-0000-0000-0000-000000000001/source.png"},
           "displayImage":{"width":160,"height":160,"url":"/api/damage-assets/00000000-0000-0000-0000-000000000001/overlay.png","coordinateSpace":"processed"},
           "processing":{"preprocessingMs":1,"inferenceMs":2,"postprocessingMs":3,"totalMs":6},
           "detections":[],"damage":{"status":"below_alarm_threshold","candidate_pixels_original":140,"found":false,"observed_surface":"front"},
           "severity":{"status":"needs_review","estimated_severity":"severe","needs_review":true,
              "heuristic_unvalidated":true,"reasons":["skeleton_length_ratio:severe","below_alarm_threshold"]},
           "assets":{"damage_original":"/api/damage-assets/00000000-0000-0000-0000-000000000001/damage_original.png"},
           "transformMatrix":[[1,0,0],[0,1,0],[0,0,1]]}
          """);
        worker = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        worker.createContext("/analyze", exchange -> {
            uploaded.set(exchange.getRequestBody().readAllBytes());
            query.set(exchange.getRequestURI().getQuery());
            byte[] body = workerResult.get().getBytes(StandardCharsets.UTF_8);
            exchange.getResponseHeaders().set("Content-Type", "application/json");
            exchange.sendResponseHeaders(200, body.length);
            exchange.getResponseBody().write(body); exchange.close();
        });
        worker.createContext("/api/damage-assets", exchange -> {
            String path = exchange.getRequestURI().getPath();
            if (path.contains("nonexistent")) {
                byte[] body = "{\"error\":\"not_found\"}".getBytes(StandardCharsets.UTF_8);
                exchange.getResponseHeaders().set("Content-Type", "application/json");
                exchange.sendResponseHeaders(404, body.length);
                exchange.getResponseBody().write(body); exchange.close();
                return;
            }
            byte[] body = new byte[]{(byte)137,80,78,71};
            exchange.sendResponseHeaders(200, body.length);
            exchange.getResponseBody().write(body); exchange.close();
        });
        worker.start();
        var client = new PythonDamageClient("http://127.0.0.1:" + worker.getAddress().getPort(), 1000, 1000);
        repository = mock(ScanRecordRepository.class);
        when(repository.save(any())).thenAnswer(call -> {
            ScanRecord scan = call.getArgument(0); scan.setId(id); stored.set(scan); return scan;
        });
        when(repository.findByIdWithDetections(id)).thenAnswer(call -> Optional.ofNullable(stored.get()));
        when(repository.findAll(any(Pageable.class))).thenAnswer(call -> {
            var s = stored.get();
            return new PageImpl<>(s == null ? List.of() : List.of(s), call.getArgument(0), s == null ? 0 : 1);
        });
        var service = new ScanService(repository, client, new ObjectMapper());
        mvc = MockMvcBuilders.standaloneSetup(new DetectionController(service), new ScanController(service), new DamageAssetController(client))
                .setControllerAdvice(new GlobalExceptionHandler()).build();
    }

    @AfterEach void tearDown() { worker.stop(0); }

    @Test void uploadsOriginalBytesPersistsEvidenceAndReturnsMasks() throws Exception {
        byte[] original = new byte[]{1,2,3,4,5};
        mvc.perform(multipart("/api/detections").file(new MockMultipartFile("image", "phone.jpg", "image/jpeg", original))
                .param("surface", "front").param("surfaceAspectRatio", "0.5").param("fullSurfaceConfirmed", "true"))
                .andExpect(status().isOk()).andExpect(jsonPath("$.scanId").value(id.toString()))
                .andExpect(jsonPath("$.severity.estimated_severity").value("severe"))
                .andExpect(jsonPath("$.damage.candidate_pixels_original").value(140))
                .andExpect(jsonPath("$.hasDefect").value(false)).andExpect(jsonPath("$.detections").isEmpty());
        assertArrayEquals(original, uploaded.get());
        assertTrue(query.get().contains("aspect=0.5") && query.get().contains("complete=true"));
        assertNotNull(stored.get().getAnalysisJson());
        mvc.perform(get("/api/detections/" + id)).andExpect(status().isOk())
                .andExpect(jsonPath("$.severity.needs_review").value(true))
                .andExpect(jsonPath("$.severity.reasons[1]").value("below_alarm_threshold"));
        mvc.perform(get("/api/damage-assets/" + id + "/damage_original.png"))
                .andExpect(status().isOk()).andExpect(content().contentType("image/png"));
    }

    @Test void preservesUnknownEvidenceAndRejectsInvalidInput() throws Exception {
        workerResult.set(workerResult.get().replace("\"hasDefect\":false", "\"hasDefect\":null")
                .replace("\"success\":true", "\"success\":false"));
        mvc.perform(multipart("/api/detections").file(new MockMultipartFile("image", new byte[]{1})))
                .andExpect(status().isOk()).andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.hasDefect").doesNotExist());
        assertNull(stored.get().getHasDefect());
        mvc.perform(multipart("/api/detections").file(new MockMultipartFile("image", new byte[]{1}))
                .param("surfaceAspectRatio", "NaN")).andExpect(status().isBadRequest());
        mvc.perform(multipart("/api/detections").file(new MockMultipartFile("image", new byte[0])))
                .andExpect(status().isBadRequest());
    }

    @Test void retrievesScanHistoryWithEnrichedMetadataAndHandlesMissingAsset() throws Exception {
        byte[] original = new byte[]{1, 2, 3};
        mvc.perform(multipart("/api/detections").file(new MockMultipartFile("image", "phone.jpg", "image/jpeg", original))
                .param("surface", "front").param("surfaceAspectRatio", "0.5").param("fullSurfaceConfirmed", "true"))
                .andExpect(status().isOk());

        // Test GET /api/scans
        mvc.perform(get("/api/scans?page=0&size=10"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.content[0].scanId").value(id.toString()))
                .andExpect(jsonPath("$.content[0].surface").value("front"))
                .andExpect(jsonPath("$.content[0].estimatedSeverity").value("severe"))
                .andExpect(jsonPath("$.content[0].needsReview").value(true))
                .andExpect(jsonPath("$.content[0].sourceImageUrl").isNotEmpty());

        // Test GET /api/scans/{id}
        mvc.perform(get("/api/scans/" + id))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.scanId").value(id.toString()))
                .andExpect(jsonPath("$.severity.status").value("needs_review"));

        // Test GET missing asset 404
        mvc.perform(get("/api/damage-assets/" + id + "/nonexistent_mask.png"))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.error").value("RESOURCE_NOT_FOUND"));
    }
}
