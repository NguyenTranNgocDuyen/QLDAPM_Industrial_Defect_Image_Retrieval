package com.industrial.defect.repository;

import com.industrial.defect.entity.ImageRetrievalRecord;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.UUID;

@Repository
public interface ImageRetrievalRepository extends JpaRepository<ImageRetrievalRecord, UUID> {

    List<ImageRetrievalRecord> findByScanIdOrderByRankOrderAsc(UUID scanId);
}
