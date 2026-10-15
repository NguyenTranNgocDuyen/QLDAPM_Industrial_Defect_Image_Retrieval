package com.industrial.defect.dto;

import java.time.OffsetDateTime;
import java.util.UUID;

public class ScanSummaryDto {

    private UUID scanId;
    private String originalFilename;
    private String displayImageUrl;
    private boolean hasDefect;
    private int detectionCount;
    private String status;
    private Double totalMs;
    private OffsetDateTime createdAt;

    public ScanSummaryDto() {
    }

    public ScanSummaryDto(UUID scanId, String originalFilename, String displayImageUrl, boolean hasDefect,
                          int detectionCount, String status, Double totalMs, OffsetDateTime createdAt) {
        this.scanId = scanId;
        this.originalFilename = originalFilename;
        this.displayImageUrl = displayImageUrl;
        this.hasDefect = hasDefect;
        this.detectionCount = detectionCount;
        this.status = status;
        this.totalMs = totalMs;
        this.createdAt = createdAt;
    }

    public UUID getScanId() {
        return scanId;
    }

    public void setScanId(UUID scanId) {
        this.scanId = scanId;
    }

    public String getOriginalFilename() {
        return originalFilename;
    }

    public void setOriginalFilename(String originalFilename) {
        this.originalFilename = originalFilename;
    }

    public String getDisplayImageUrl() {
        return displayImageUrl;
    }

    public void setDisplayImageUrl(String displayImageUrl) {
        this.displayImageUrl = displayImageUrl;
    }

    public boolean isHasDefect() {
        return hasDefect;
    }

    public void setHasDefect(boolean hasDefect) {
        this.hasDefect = hasDefect;
    }

    public int getDetectionCount() {
        return detectionCount;
    }

    public void setDetectionCount(int detectionCount) {
        this.detectionCount = detectionCount;
    }

    public String getStatus() {
        return status;
    }

    public void setStatus(String status) {
        this.status = status;
    }

    public Double getTotalMs() {
        return totalMs;
    }

    public void setTotalMs(Double totalMs) {
        this.totalMs = totalMs;
    }

    public OffsetDateTime getCreatedAt() {
        return createdAt;
    }

    public void setCreatedAt(OffsetDateTime createdAt) {
        this.createdAt = createdAt;
    }
}
