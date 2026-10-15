package com.industrial.defect.repository;

import com.industrial.defect.entity.DefectDetection;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.UUID;

@Repository
public interface DefectDetectionRepository extends JpaRepository<DefectDetection, UUID> {

    List<DefectDetection> findByScanId(UUID scanId);

    List<DefectDetection> findByDefectClass(String defectClass);
}
