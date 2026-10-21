package com.industrial.defect.dto;

import java.time.OffsetDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

public class InspectionSessionDto {
    private UUID sessionId;
    private OffsetDateTime createdAt;
    private String deviceInfo;
    private Boolean hasDefect;
    private String overallSeverity;
    private Boolean needsReview;
    private ScanSummaryDto frontScan;
    private ScanSummaryDto backScan;
    private List<ScanSummaryDto> otherScans = new ArrayList<>();

    public InspectionSessionDto() {
    }

    public UUID getSessionId() {
        return sessionId;
    }

    public void setSessionId(UUID sessionId) {
        this.sessionId = sessionId;
    }

    public OffsetDateTime getCreatedAt() {
        return createdAt;
    }

    public void setCreatedAt(OffsetDateTime createdAt) {
        this.createdAt = createdAt;
    }

    public String getDeviceInfo() {
        return deviceInfo;
    }

    public void setDeviceInfo(String deviceInfo) {
        this.deviceInfo = deviceInfo;
    }

    public Boolean getHasDefect() {
        return hasDefect;
    }

    public void setHasDefect(Boolean hasDefect) {
        this.hasDefect = hasDefect;
    }

    public String getOverallSeverity() {
        return overallSeverity;
    }

    public void setOverallSeverity(String overallSeverity) {
        this.overallSeverity = overallSeverity;
    }

    public Boolean getNeedsReview() {
        return needsReview;
    }

    public void setNeedsReview(Boolean needsReview) {
        this.needsReview = needsReview;
    }

    public ScanSummaryDto getFrontScan() {
        return frontScan;
    }

    public void setFrontScan(ScanSummaryDto frontScan) {
        this.frontScan = frontScan;
    }

    public ScanSummaryDto getBackScan() {
        return backScan;
    }

    public void setBackScan(ScanSummaryDto backScan) {
        this.backScan = backScan;
    }

    public List<ScanSummaryDto> getOtherScans() {
        return otherScans;
    }

    public void setOtherScans(List<ScanSummaryDto> otherScans) {
        this.otherScans = otherScans;
    }
}
