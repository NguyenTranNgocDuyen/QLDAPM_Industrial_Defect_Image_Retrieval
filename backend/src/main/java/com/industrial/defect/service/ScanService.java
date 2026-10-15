package com.industrial.defect.service;

import com.industrial.defect.dto.*;
import com.industrial.defect.entity.DefectDetection;
import com.industrial.defect.entity.ScanRecord;
import com.industrial.defect.exception.ResourceNotFoundException;
import com.industrial.defect.repository.DefectDetectionRepository;
import com.industrial.defect.repository.ScanRecordRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.multipart.MultipartFile;

import javax.imageio.ImageIO;
import java.awt.image.BufferedImage;
import java.io.IOException;
import java.time.OffsetDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;
import java.util.stream.Collectors;

@Service
public class ScanService {

    private static final Logger log = LoggerFactory.getLogger(ScanService.class);

    private final ScanRecordRepository scanRepository;
    private final DefectDetectionRepository detectionRepository;

    public ScanService(ScanRecordRepository scanRepository, DefectDetectionRepository detectionRepository) {
        this.scanRepository = scanRepository;
        this.detectionRepository = detectionRepository;
    }

    @Transactional(readOnly = true)
    public DetectionResponseDto getDetectionResult(UUID scanId) {
        ScanRecord scan = scanRepository.findByIdWithDetections(scanId)
                .orElseThrow(() -> new ResourceNotFoundException("Scan not found with id: " + scanId));

        return toDetectionResponseDto(scan);
    }

    @Transactional(readOnly = true)
    public Page<ScanSummaryDto> getScanHistory(Boolean hasDefect, Pageable pageable) {
        Page<ScanRecord> page = (hasDefect != null)
                ? scanRepository.findByHasDefect(hasDefect, pageable)
                : scanRepository.findAll(pageable);

        return page.map(scan -> new ScanSummaryDto(
                scan.getId(),
                scan.getOriginalFilename(),
                scan.getDisplayImageUrl(),
                scan.getHasDefect(),
                scan.getDetections().size(),
                scan.getStatus(),
                scan.getTotalMs(),
                scan.getCreatedAt()
        ));
    }

    @Transactional
    public DetectionResponseDto processImageUpload(MultipartFile file, String deviceInfo) {
        if (file.isEmpty()) {
            throw new IllegalArgumentException("Uploaded image cannot be empty");
        }

        long startTime = System.currentTimeMillis();
        int width = 1280;
        int height = 720;

        try {
            BufferedImage img = ImageIO.read(file.getInputStream());
            if (img != null) {
                width = img.getWidth();
                height = img.getHeight();
            }
        } catch (IOException e) {
            log.warn("Could not read image dimensions, fallback to default {}: {}", width + "x" + height, e.getMessage());
        }

        UUID scanId = UUID.randomUUID();
        String displayUrl = "/api/scans/" + scanId + "/image";

        ScanRecord scan = new ScanRecord();
        scan.setId(scanId);
        scan.setOriginalFilename(file.getOriginalFilename());
        scan.setSourceImageUrl("/api/scans/" + scanId + "/source");
        scan.setSourceWidth(width);
        scan.setSourceHeight(height);
        scan.setDisplayImageUrl(displayUrl);
        scan.setDisplayWidth(width);
        scan.setDisplayHeight(height);
        scan.setCoordinateSpace("processed");
        scan.setSuccess(true);
        scan.setStatus("COMPLETED");
        scan.setDeviceInfo(deviceInfo != null ? deviceInfo : "Standard-Camera");

        // Processing timing metrics (baseline simulation until python service is bound)
        double prepMs = 12.0 + Math.random() * 5.0;
        double inferMs = 45.0 + Math.random() * 20.0;
        double postMs = 3.5 + Math.random() * 2.0;
        double totalMs = prepMs + inferMs + postMs;

        scan.setPreprocessingMs(Math.round(prepMs * 10.0) / 10.0);
        scan.setInferenceMs(Math.round(inferMs * 10.0) / 10.0);
        scan.setPostprocessingMs(Math.round(postMs * 10.0) / 10.0);
        scan.setTotalMs(Math.round(totalMs * 10.0) / 10.0);

        // Baseline simulated detection for demonstration
        List<DefectDetection> detections = new ArrayList<>();
        DefectDetection sampleDet = new DefectDetection();
        sampleDet.setId(UUID.randomUUID());
        sampleDet.setScan(scan);
        sampleDet.setDefectClass("scratch");
        sampleDet.setConfidence(0.92);
        sampleDet.setX1(Math.min(100.0, width * 0.1));
        sampleDet.setY1(Math.min(80.0, height * 0.1));
        sampleDet.setX2(Math.min(320.0, width * 0.4));
        sampleDet.setY2(Math.min(220.0, height * 0.3));
        sampleDet.setCreatedAt(OffsetDateTime.now());
        detections.add(sampleDet);

        scan.setHasDefect(!detections.isEmpty());
        scan.setDetections(detections);

        ScanRecord saved = scanRepository.save(scan);
        return toDetectionResponseDto(saved);
    }

    private DetectionResponseDto toDetectionResponseDto(ScanRecord scan) {
        ImageSizeDto sourceSize = new ImageSizeDto(scan.getSourceWidth(), scan.getSourceHeight());
        ImageSizeDto displaySize = new ImageSizeDto(
                scan.getDisplayWidth(),
                scan.getDisplayHeight(),
                scan.getDisplayImageUrl(),
                scan.getCoordinateSpace()
        );

        ProcessingTimingDto timing = new ProcessingTimingDto(
                scan.getPreprocessingMs() != null ? scan.getPreprocessingMs() : 0.0,
                scan.getInferenceMs() != null ? scan.getInferenceMs() : 0.0,
                scan.getPostprocessingMs() != null ? scan.getPostprocessingMs() : 0.0,
                scan.getTotalMs() != null ? scan.getTotalMs() : 0.0
        );

        List<DetectionItemDto> items = scan.getDetections().stream()
                .map(d -> new DetectionItemDto(
                        d.getDefectClass(),
                        d.getConfidence(),
                        d.getX1(),
                        d.getY1(),
                        d.getX2(),
                        d.getY2()
                ))
                .collect(Collectors.toList());

        return new DetectionResponseDto(
                scan.getId(),
                scan.getSuccess(),
                scan.getHasDefect(),
                sourceSize,
                displaySize,
                timing,
                items
        );
    }
}
