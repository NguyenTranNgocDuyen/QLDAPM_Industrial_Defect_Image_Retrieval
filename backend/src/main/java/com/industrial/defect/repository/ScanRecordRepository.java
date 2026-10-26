package com.industrial.defect.repository;

import com.industrial.defect.entity.ScanRecord;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

@Repository
public interface ScanRecordRepository extends JpaRepository<ScanRecord, UUID> {

    @Query("SELECT s FROM ScanRecord s LEFT JOIN FETCH s.detections WHERE s.id = :id")
    Optional<ScanRecord> findByIdWithDetections(@Param("id") UUID id);

    Page<ScanRecord> findByHasDefect(Boolean hasDefect, Pageable pageable);

    long countByHasDefect(Boolean hasDefect);

    @Query("SELECT s FROM ScanRecord s WHERE s.createdAt >= :start AND s.createdAt < :end ORDER BY s.createdAt DESC")
    List<ScanRecord> findByCreatedAtBetween(@Param("start") java.time.OffsetDateTime start, @Param("end") java.time.OffsetDateTime end);

    @Query("SELECT s FROM ScanRecord s WHERE s.sessionId = :sessionId ORDER BY s.createdAt ASC")
    List<ScanRecord> findBySessionId(@Param("sessionId") UUID sessionId);

    @Query("SELECT s FROM ScanRecord s ORDER BY s.createdAt DESC")
    List<ScanRecord> findAllOrderByCreatedAtDesc();
}
