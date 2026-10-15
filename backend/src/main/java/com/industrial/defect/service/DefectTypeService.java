package com.industrial.defect.service;

import com.industrial.defect.dto.DefectTypeDto;
import com.industrial.defect.entity.DefectType;
import com.industrial.defect.repository.DefectTypeRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.stream.Collectors;

@Service
public class DefectTypeService {

    private final DefectTypeRepository defectTypeRepository;

    public DefectTypeService(DefectTypeRepository defectTypeRepository) {
        this.defectTypeRepository = defectTypeRepository;
    }

    @Transactional(readOnly = true)
    public List<DefectTypeDto> getAllActiveTypes() {
        return defectTypeRepository.findByIsActiveTrue().stream()
                .map(t -> new DefectTypeDto(
                        t.getCode(),
                        t.getName(),
                        t.getDescription(),
                        t.getSeverity(),
                        t.getBoundingBoxColor()
                ))
                .collect(Collectors.toList());
    }
}
