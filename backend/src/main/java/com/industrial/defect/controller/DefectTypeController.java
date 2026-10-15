package com.industrial.defect.controller;

import com.industrial.defect.dto.DefectTypeDto;
import com.industrial.defect.service.DefectTypeService;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@RequestMapping("/api/defect-types")
public class DefectTypeController {

    private final DefectTypeService defectTypeService;

    public DefectTypeController(DefectTypeService defectTypeService) {
        this.defectTypeService = defectTypeService;
    }

    @GetMapping
    public ResponseEntity<List<DefectTypeDto>> getDefectTypes() {
        return ResponseEntity.ok(defectTypeService.getAllActiveTypes());
    }
}
