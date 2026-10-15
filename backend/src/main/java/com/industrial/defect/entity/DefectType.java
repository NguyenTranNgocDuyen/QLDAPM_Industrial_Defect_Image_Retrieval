package com.industrial.defect.entity;

import jakarta.persistence.*;
import java.time.OffsetDateTime;

@Entity
@Table(name = "defect_types")
public class DefectType {

    @Id
    @Column(name = "code", length = 50, nullable = false)
    private String code;

    @Column(name = "name", length = 100, nullable = false)
    private String name;

    @Column(name = "description", columnDefinition = "TEXT")
    private String description;

    @Column(name = "severity", length = 20, nullable = false)
    private String severity = "MEDIUM";

    @Column(name = "bounding_box_color", length = 10)
    private String boundingBoxColor = "#FF0000";

    @Column(name = "is_active", nullable = false)
    private Boolean isActive = true;

    @Column(name = "created_at")
    private OffsetDateTime createdAt;

    public DefectType() {
    }

    public DefectType(String code, String name, String description, String severity, String boundingBoxColor, Boolean isActive) {
        this.code = code;
        this.name = name;
        this.description = description;
        this.severity = severity != null ? severity : "MEDIUM";
        this.boundingBoxColor = boundingBoxColor != null ? boundingBoxColor : "#FF0000";
        this.isActive = isActive != null ? isActive : true;
    }

    @PrePersist
    public void prePersist() {
        if (this.createdAt == null) {
            this.createdAt = OffsetDateTime.now();
        }
    }

    public String getCode() {
        return code;
    }

    public void setCode(String code) {
        this.code = code;
    }

    public String getName() {
        return name;
    }

    public void setName(String name) {
        this.name = name;
    }

    public String getDescription() {
        return description;
    }

    public void setDescription(String description) {
        this.description = description;
    }

    public String getSeverity() {
        return severity;
    }

    public void setSeverity(String severity) {
        this.severity = severity;
    }

    public String getBoundingBoxColor() {
        return boundingBoxColor;
    }

    public void setBoundingBoxColor(String boundingBoxColor) {
        this.boundingBoxColor = boundingBoxColor;
    }

    public Boolean getIsActive() {
        return isActive;
    }

    public void setIsActive(Boolean isActive) {
        this.isActive = isActive;
    }

    public OffsetDateTime getCreatedAt() {
        return createdAt;
    }

    public void setCreatedAt(OffsetDateTime createdAt) {
        this.createdAt = createdAt;
    }
}
