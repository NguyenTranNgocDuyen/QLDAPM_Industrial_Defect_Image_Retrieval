package com.industrial.defect.dto;

import java.util.ArrayList;
import java.util.List;
import java.util.UUID;
import java.util.Map;

public class DetectionResponseDto {

    private UUID scanId;
    private boolean success;
    private Boolean hasDefect;
    private String status;
    private Map<String, Object> damage;
    private Map<String, Object> severity;
    private Map<String, String> assets;
    private List<List<Double>> transformMatrix;
    private ImageSizeDto sourceImage;
    private ImageSizeDto displayImage;
    private ProcessingTimingDto processing;
    private List<DetectionItemDto> detections = new ArrayList<>();

    public DetectionResponseDto() {
    }

    public DetectionResponseDto(UUID scanId, boolean success, Boolean hasDefect, ImageSizeDto sourceImage,
                                ImageSizeDto displayImage, ProcessingTimingDto processing,
                                List<DetectionItemDto> detections) {
        this.scanId = scanId;
        this.success = success;
        this.hasDefect = hasDefect;
        this.sourceImage = sourceImage;
        this.displayImage = displayImage;
        this.processing = processing;
        this.detections = detections != null ? detections : new ArrayList<>();
    }

    public UUID getScanId() {
        return scanId;
    }

    public void setScanId(UUID scanId) {
        this.scanId = scanId;
    }

    public boolean isSuccess() {
        return success;
    }

    public void setSuccess(boolean success) {
        this.success = success;
    }

    public Boolean isHasDefect() {
        return hasDefect;
    }

    public void setHasDefect(Boolean hasDefect) {
        this.hasDefect = hasDefect;
    }

    public ImageSizeDto getSourceImage() {
        return sourceImage;
    }

    public void setSourceImage(ImageSizeDto sourceImage) {
        this.sourceImage = sourceImage;
    }

    public ImageSizeDto getDisplayImage() {
        return displayImage;
    }

    public void setDisplayImage(ImageSizeDto displayImage) {
        this.displayImage = displayImage;
    }

    public ProcessingTimingDto getProcessing() {
        return processing;
    }

    public void setProcessing(ProcessingTimingDto processing) {
        this.processing = processing;
    }

    public List<DetectionItemDto> getDetections() {
        return detections;
    }

    public void setDetections(List<DetectionItemDto> detections) {
        this.detections = detections;
    }

    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }
    public Map<String, Object> getDamage() { return damage; }
    public void setDamage(Map<String, Object> damage) { this.damage = damage; }
    public Map<String, Object> getSeverity() { return severity; }
    public void setSeverity(Map<String, Object> severity) { this.severity = severity; }
    public Map<String, String> getAssets() { return assets; }
    public void setAssets(Map<String, String> assets) { this.assets = assets; }
    public List<List<Double>> getTransformMatrix() { return transformMatrix; }
    public void setTransformMatrix(List<List<Double>> matrix) { this.transformMatrix = matrix; }
}
