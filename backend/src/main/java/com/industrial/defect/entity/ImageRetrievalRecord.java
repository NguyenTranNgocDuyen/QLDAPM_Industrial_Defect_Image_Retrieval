package com.industrial.defect.entity;

import com.fasterxml.jackson.annotation.JsonIgnore;
import jakarta.persistence.*;
import java.time.OffsetDateTime;
import java.util.UUID;

@Entity
@Table(name = "image_retrievals")
public class ImageRetrievalRecord {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    @Column(name = "id", nullable = false, updatable = false)
    private UUID id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "scan_id", nullable = false)
    @JsonIgnore
    private ScanRecord scan;

    @Column(name = "gallery_item_id")
    private UUID galleryItemId;

    @Column(name = "reference_image_url", length = 500, nullable = false)
    private String referenceImageUrl;

    @Column(name = "matched_defect_type", length = 50, nullable = false)
    private String matchedDefectType;

    @Column(name = "similarity_score", nullable = false)
    private Double similarityScore;

    @Column(name = "rank_order", nullable = false)
    private Integer rankOrder = 1;

    @Column(name = "created_at")
    private OffsetDateTime createdAt;

    public ImageRetrievalRecord() {
    }

    public ImageRetrievalRecord(String referenceImageUrl, String matchedDefectType, Double similarityScore, Integer rankOrder) {
        this.referenceImageUrl = referenceImageUrl;
        this.matchedDefectType = matchedDefectType;
        this.similarityScore = similarityScore;
        this.rankOrder = rankOrder;
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

    public UUID getGalleryItemId() {
        return galleryItemId;
    }

    public void setGalleryItemId(UUID galleryItemId) {
        this.galleryItemId = galleryItemId;
    }

    public String getReferenceImageUrl() {
        return referenceImageUrl;
    }

    public void setReferenceImageUrl(String referenceImageUrl) {
        this.referenceImageUrl = referenceImageUrl;
    }

    public String getMatchedDefectType() {
        return matchedDefectType;
    }

    public void setMatchedDefectType(String matchedDefectType) {
        this.matchedDefectType = matchedDefectType;
    }

    public Double getSimilarityScore() {
        return similarityScore;
    }

    public void setSimilarityScore(Double similarityScore) {
        this.similarityScore = similarityScore;
    }

    public Integer getRankOrder() {
        return rankOrder;
    }

    public void setRankOrder(Integer rankOrder) {
        this.rankOrder = rankOrder;
    }

    public OffsetDateTime getCreatedAt() {
        return createdAt;
    }

    public void setCreatedAt(OffsetDateTime createdAt) {
        this.createdAt = createdAt;
    }
}
