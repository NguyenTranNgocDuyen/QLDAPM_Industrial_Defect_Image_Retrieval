package com.industrial.defect.dto;

import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

public class DetectionResponseDto {

    private UUID scanId;
    private boolean success;
    private boolean hasDefect;
    private ImageSizeDto sourceImage;
    private ImageSizeDto displayImage;
    private ProcessingTimingDto processing;
    private List<DetectionItemDto> detections = new ArrayList<>();

    public DetectionResponseDto() {
    }

    public DetectionResponseDto(UUID scanId, boolean success, boolean hasDefect, ImageSizeDto sourceImage,
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

    public boolean isHasDefect() {
        return hasDefect;
    }

    public void setHasDefect(boolean hasDefect) {
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
}
