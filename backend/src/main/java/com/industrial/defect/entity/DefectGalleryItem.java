package com.industrial.defect.entity;

import jakarta.persistence.*;
import java.time.OffsetDateTime;
import java.util.UUID;

@Entity
@Table(name = "defect_gallery")
public class DefectGalleryItem {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    @Column(name = "id", nullable = false, updatable = false)
    private UUID id;

    @Column(name = "title", length = 150, nullable = false)
    private String title;

    @Column(name = "image_url", length = 500, nullable = false)
    private String imageUrl;

    @Column(name = "defect_class", length = 50, nullable = false)
    private String defectClass;

    @Column(name = "component_type", length = 100)
    private String componentType;

    @Column(name = "description", columnDefinition = "TEXT")
    private String description;

    @Column(name = "embedding_vector", columnDefinition = "TEXT")
    private String embeddingVector;

    @Column(name = "created_at")
    private OffsetDateTime createdAt;

    public DefectGalleryItem() {
    }

    public DefectGalleryItem(String title, String imageUrl, String defectClass, String componentType, String description) {
        this.title = title;
        this.imageUrl = imageUrl;
        this.defectClass = defectClass;
        this.componentType = componentType;
        this.description = description;
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

    public String getTitle() {
        return title;
    }

    public void setTitle(String title) {
        this.title = title;
    }

    public String getImageUrl() {
        return imageUrl;
    }

    public void setImageUrl(String imageUrl) {
        this.imageUrl = imageUrl;
    }

    public String getDefectClass() {
        return defectClass;
    }

    public void setDefectClass(String defectClass) {
        this.defectClass = defectClass;
    }

    public String getComponentType() {
        return componentType;
    }

    public void setComponentType(String componentType) {
        this.componentType = componentType;
    }

    public String getDescription() {
        return description;
    }

    public void setDescription(String description) {
        this.description = description;
    }

    public String getEmbeddingVector() {
        return embeddingVector;
    }

    public void setEmbeddingVector(String embeddingVector) {
        this.embeddingVector = embeddingVector;
    }

    public OffsetDateTime getCreatedAt() {
        return createdAt;
    }

    public void setCreatedAt(OffsetDateTime createdAt) {
        this.createdAt = createdAt;
    }
}
