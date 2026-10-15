package com.industrial.defect.entity;

import jakarta.persistence.*;
import java.time.OffsetDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

@Entity
@Table(name = "scans")
public class ScanRecord {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    @Column(name = "id", nullable = false, updatable = false)
    private UUID id;

    @Column(name = "original_filename")
    private String originalFilename;

    @Column(name = "source_image_url", length = 500)
    private String sourceImageUrl;

    @Column(name = "source_width", nullable = false)
    private Integer sourceWidth = 0;

    @Column(name = "source_height", nullable = false)
    private Integer sourceHeight = 0;

    @Column(name = "display_image_url", length = 500)
    private String displayImageUrl;

    @Column(name = "display_width", nullable = false)
    private Integer displayWidth = 0;

    @Column(name = "display_height", nullable = false)
    private Integer displayHeight = 0;

    @Column(name = "coordinate_space", length = 20, nullable = false)
    private String coordinateSpace = "processed";

    @Column(name = "has_defect", nullable = false)
    private Boolean hasDefect = false;

    @Column(name = "success", nullable = false)
    private Boolean success = true;

    @Column(name = "status", length = 30, nullable = false)
    private String status = "COMPLETED";

    @Column(name = "error_message", columnDefinition = "TEXT")
    private String errorMessage;

    @Column(name = "device_info", length = 100)
    private String deviceInfo;

    @Column(name = "preprocessing_ms")
    private Double preprocessingMs = 0.0;

    @Column(name = "inference_ms")
    private Double inferenceMs = 0.0;

    @Column(name = "postprocessing_ms")
    private Double postprocessingMs = 0.0;

    @Column(name = "total_ms")
    private Double totalMs = 0.0;

    @Column(name = "created_at")
    private OffsetDateTime createdAt;

    @Column(name = "updated_at")
    private OffsetDateTime updatedAt;

    @OneToMany(mappedBy = "scan", cascade = CascadeType.ALL, orphanRemoval = true, fetch = FetchType.LAZY)
    private List<DefectDetection> detections = new ArrayList<>();

    @OneToMany(mappedBy = "scan", cascade = CascadeType.ALL, orphanRemoval = true, fetch = FetchType.LAZY)
    private List<ImageRetrievalRecord> retrievals = new ArrayList<>();

    public ScanRecord() {
    }

    @PrePersist
    public void prePersist() {
        OffsetDateTime now = OffsetDateTime.now();
        if (this.createdAt == null) {
            this.createdAt = now;
        }
        if (this.updatedAt == null) {
            this.updatedAt = now;
        }
    }

    @PreUpdate
    public void preUpdate() {
        this.updatedAt = OffsetDateTime.now();
    }

    public void addDetection(DefectDetection detection) {
        detections.add(detection);
        detection.setScan(this);
    }

    public void removeDetection(DefectDetection detection) {
        detections.remove(detection);
        detection.setScan(null);
    }

    public void addRetrieval(ImageRetrievalRecord retrieval) {
        retrievals.add(retrieval);
        retrieval.setScan(this);
    }

    // Getters and Setters

    public UUID getId() {
        return id;
    }

    public void setId(UUID id) {
        this.id = id;
    }

    public String getOriginalFilename() {
        return originalFilename;
    }

    public void setOriginalFilename(String originalFilename) {
        this.originalFilename = originalFilename;
    }

    public String getSourceImageUrl() {
        return sourceImageUrl;
    }

    public void setSourceImageUrl(String sourceImageUrl) {
        this.sourceImageUrl = sourceImageUrl;
    }

    public Integer getSourceWidth() {
        return sourceWidth;
    }

    public void setSourceWidth(Integer sourceWidth) {
        this.sourceWidth = sourceWidth;
    }

    public Integer getSourceHeight() {
        return sourceHeight;
    }

    public void setSourceHeight(Integer sourceHeight) {
        this.sourceHeight = sourceHeight;
    }

    public String getDisplayImageUrl() {
        return displayImageUrl;
    }

    public void setDisplayImageUrl(String displayImageUrl) {
        this.displayImageUrl = displayImageUrl;
    }

    public Integer getDisplayWidth() {
        return displayWidth;
    }

    public void setDisplayWidth(Integer displayWidth) {
        this.displayWidth = displayWidth;
    }

    public Integer getDisplayHeight() {
        return displayHeight;
    }

    public void setDisplayHeight(Integer displayHeight) {
        this.displayHeight = displayHeight;
    }

    public String getCoordinateSpace() {
        return coordinateSpace;
    }

    public void setCoordinateSpace(String coordinateSpace) {
        this.coordinateSpace = coordinateSpace;
    }

    public Boolean getHasDefect() {
        return hasDefect;
    }

    public void setHasDefect(Boolean hasDefect) {
        this.hasDefect = hasDefect;
    }

    public Boolean getSuccess() {
        return success;
    }

    public void setSuccess(Boolean success) {
        this.success = success;
    }

    public String getStatus() {
        return status;
    }

    public void setStatus(String status) {
        this.status = status;
    }

    public String getErrorMessage() {
        return errorMessage;
    }

    public void setErrorMessage(String errorMessage) {
        this.errorMessage = errorMessage;
    }

    public String getDeviceInfo() {
        return deviceInfo;
    }

    public void setDeviceInfo(String deviceInfo) {
        this.deviceInfo = deviceInfo;
    }

    public Double getPreprocessingMs() {
        return preprocessingMs;
    }

    public void setPreprocessingMs(Double preprocessingMs) {
        this.preprocessingMs = preprocessingMs;
    }

    public Double getInferenceMs() {
        return inferenceMs;
    }

    public void setInferenceMs(Double inferenceMs) {
        this.inferenceMs = inferenceMs;
    }

    public Double getPostprocessingMs() {
        return postprocessingMs;
    }

    public void setPostprocessingMs(Double postprocessingMs) {
        this.postprocessingMs = postprocessingMs;
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

    public OffsetDateTime getUpdatedAt() {
        return updatedAt;
    }

    public void setUpdatedAt(OffsetDateTime updatedAt) {
        this.updatedAt = updatedAt;
    }

    public List<DefectDetection> getDetections() {
        return detections;
    }

    public void setDetections(List<DefectDetection> detections) {
        this.detections = detections;
    }

    public List<ImageRetrievalRecord> getRetrievals() {
        return retrievals;
    }

    public void setRetrievals(List<ImageRetrievalRecord> retrievals) {
        this.retrievals = retrievals;
    }
}
