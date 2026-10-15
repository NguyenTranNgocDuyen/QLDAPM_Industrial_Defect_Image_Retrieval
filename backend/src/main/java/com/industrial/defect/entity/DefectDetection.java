package com.industrial.defect.entity;

import com.fasterxml.jackson.annotation.JsonIgnore;
import jakarta.persistence.*;
import java.time.OffsetDateTime;
import java.util.UUID;

@Entity
@Table(name = "defect_detections")
public class DefectDetection {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    @Column(name = "id", nullable = false, updatable = false)
    private UUID id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "scan_id", nullable = false)
    @JsonIgnore
    private ScanRecord scan;

    @Column(name = "defect_class", length = 50, nullable = false)
    private String defectClass;

    @Column(name = "confidence", nullable = false)
    private Double confidence;

    @Column(name = "x1", nullable = false)
    private Double x1;

    @Column(name = "y1", nullable = false)
    private Double y1;

    @Column(name = "x2", nullable = false)
    private Double x2;

    @Column(name = "y2", nullable = false)
    private Double y2;

    @Column(name = "created_at")
    private OffsetDateTime createdAt;

    public DefectDetection() {
    }

    public DefectDetection(String defectClass, Double confidence, Double x1, Double y1, Double x2, Double y2) {
        this.defectClass = defectClass;
        this.confidence = confidence;
        this.x1 = x1;
        this.y1 = y1;
        this.x2 = x2;
        this.y2 = y2;
    }

    @PrePersist
    public void prePersist() {
        if (this.createdAt == null) {
            this.createdAt = OffsetDateTime.now();
        }
    }

    public UUID getId() {
        return id;
    }

    public void setId(UUID id) {
        this.id = id;
    }

    public ScanRecord getScan() {
        return scan;
    }

    public void setScan(ScanRecord scan) {
        this.scan = scan;
    }

    public String getDefectClass() {
        return defectClass;
    }

    public void setDefectClass(String defectClass) {
        this.defectClass = defectClass;
    }

    public Double getConfidence() {
        return confidence;
    }

    public void setConfidence(Double confidence) {
        this.confidence = confidence;
    }

    public Double getX1() {
        return x1;
    }

    public void setX1(Double x1) {
        this.x1 = x1;
    }

    public Double getY1() {
        return y1;
    }

    public void setY1(Double y1) {
        this.y1 = y1;
    }

    public Double getX2() {
        return x2;
    }

    public void setX2(Double x2) {
        this.x2 = x2;
    }

    public Double getY2() {
        return y2;
    }

    public void setY2(Double y2) {
        this.y2 = y2;
    }

    public OffsetDateTime getCreatedAt() {
        return createdAt;
    }

    public void setCreatedAt(OffsetDateTime createdAt) {
        this.createdAt = createdAt;
    }
}
