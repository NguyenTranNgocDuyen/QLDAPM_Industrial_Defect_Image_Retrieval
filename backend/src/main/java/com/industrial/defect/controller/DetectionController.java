package com.industrial.defect.controller;

import com.industrial.defect.dto.DetectionResponseDto;
import com.industrial.defect.service.ScanService;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.util.UUID;

@RestController
@RequestMapping("/api/detections")
public class DetectionController {

    private final ScanService scanService;

    public DetectionController(ScanService scanService) {
        this.scanService = scanService;
    }

    /**
     * POST /api/detections
     * Contract conforming endpoint for image defect detection.
     */
    @PostMapping(consumes = MediaType.MULTIPART_FORM_DATA_VALUE, produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<DetectionResponseDto> uploadAndDetect(
            @RequestParam("image") MultipartFile image,
            @RequestParam(value = "deviceInfo", required = false) String deviceInfo,
            @RequestParam(value = "surface", defaultValue = "unknown") String surface,
            @RequestParam(value = "surfaceAspectRatio", required = false) Double aspect,
            @RequestParam(value = "fullSurfaceConfirmed", defaultValue = "false") boolean complete,
            @RequestParam(value = "sessionId", required = false) UUID sessionId) {
        DetectionResponseDto response = scanService.processImageUpload(image, deviceInfo, surface, aspect, complete, sessionId);
        return ResponseEntity.ok(response);
    }

    /**
     * GET /api/detections/{scanId}
     * Retrieves detection result JSON by scan ID.
     */
    @GetMapping(value = "/{scanId}", produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<DetectionResponseDto> getDetectionById(@PathVariable("scanId") UUID scanId) {
        DetectionResponseDto response = scanService.getDetectionResult(scanId);
        return ResponseEntity.ok(response);
    }
}
