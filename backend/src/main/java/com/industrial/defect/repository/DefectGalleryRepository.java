package com.industrial.defect.repository;

import com.industrial.defect.entity.DefectGalleryItem;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.UUID;

@Repository
public interface DefectGalleryRepository extends JpaRepository<DefectGalleryItem, UUID> {

    List<DefectGalleryItem> findByDefectClass(String defectClass);
}
