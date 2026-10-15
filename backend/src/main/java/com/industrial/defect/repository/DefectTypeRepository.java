package com.industrial.defect.repository;

import com.industrial.defect.entity.DefectType;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public interface DefectTypeRepository extends JpaRepository<DefectType, String> {

    List<DefectType> findByIsActiveTrue();
}
