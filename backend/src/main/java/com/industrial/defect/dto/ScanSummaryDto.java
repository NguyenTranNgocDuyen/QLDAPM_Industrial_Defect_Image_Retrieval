package com.industrial.defect.dto;

import java.time.OffsetDateTime;
import java.util.UUID;

public class ScanSummaryDto {

    private UUID scanId;
    private UUID sessionId;
    private String originalFilename;
    private String displayImageUrl;
    private String sourceImageUrl;
    private String surface;
    private String estimatedSeverity;
    private Boolean needsReview;
    private Boolean hasDefect;
    private int detectionCount;
    private String status;
    private Double totalMs;
    private OffsetDateTime createdAt;

    public ScanSummaryDto() {
    }

    public ScanSummaryDto(UUID scanId, String originalFilename, String displayImageUrl, Boolean hasDefect,
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

    public UUID getSessionId() {
        return sessionId;
    }

    public void setSessionId(UUID sessionId) {
        this.sessionId = sessionId;
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

    public String getSourceImageUrl() {
        return sourceImageUrl;
    }

    public void setSourceImageUrl(String sourceImageUrl) {
        this.sourceImageUrl = sourceImageUrl;
    }

    public String getSurface() {
        return surface;
    }

    public void setSurface(String surface) {
        this.surface = surface;
    }

    public String getEstimatedSeverity() {
        return estimatedSeverity;
    }

    public void setEstimatedSeverity(String estimatedSeverity) {
        this.estimatedSeverity = estimatedSeverity;
    }

    public Boolean getNeedsReview() {
        return needsReview;
    }

    public void setNeedsReview(Boolean needsReview) {
        this.needsReview = needsReview;
    }

    public Boolean isHasDefect() {
        return hasDefect;
    }

    public void setHasDefect(Boolean hasDefect) {
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
