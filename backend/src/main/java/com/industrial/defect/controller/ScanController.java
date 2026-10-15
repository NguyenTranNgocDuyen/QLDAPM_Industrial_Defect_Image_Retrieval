package com.industrial.defect.controller;

import com.industrial.defect.dto.DetectionResponseDto;
import com.industrial.defect.dto.ScanSummaryDto;
import com.industrial.defect.service.ScanService;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.data.domain.Sort;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.UUID;

@RestController
@RequestMapping("/api/scans")
public class ScanController {

    private final ScanService scanService;

    public ScanController(ScanService scanService) {
        this.scanService = scanService;
    }

    /**
     * GET /api/scans
     * Paginated scan history with optional filtering by hasDefect.
     */
    @GetMapping
    public ResponseEntity<Page<ScanSummaryDto>> getScans(
            @RequestParam(value = "hasDefect", required = false) Boolean hasDefect,
            @RequestParam(value = "page", defaultValue = "0") int page,
            @RequestParam(value = "size", defaultValue = "20") int size,
            @RequestParam(value = "sortBy", defaultValue = "createdAt") String sortBy,
            @RequestParam(value = "sortDir", defaultValue = "desc") String sortDir) {

        Sort sort = sortDir.equalsIgnoreCase("asc")
                ? Sort.by(sortBy).ascending()
                : Sort.by(sortBy).descending();

        Pageable pageable = PageRequest.of(page, size, sort);
        Page<ScanSummaryDto> results = scanService.getScanHistory(hasDefect, pageable);
        return ResponseEntity.ok(results);
    }

    /**
     * GET /api/scans/{scanId}
     * Retrieves detailed scan and detection metrics.
     */
    @GetMapping("/{scanId}")
    public ResponseEntity<DetectionResponseDto> getScanDetail(@PathVariable("scanId") UUID scanId) {
        DetectionResponseDto result = scanService.getDetectionResult(scanId);
        return ResponseEntity.ok(result);
    }
}
