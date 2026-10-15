package com.industrial.defect.dto;

public class DefectTypeDto {

    private String code;
    private String name;
    private String description;
    private String severity;
    private String boundingBoxColor;

    public DefectTypeDto() {
    }

    public DefectTypeDto(String code, String name, String description, String severity, String boundingBoxColor) {
        this.code = code;
        this.name = name;
        this.description = description;
        this.severity = severity;
        this.boundingBoxColor = boundingBoxColor;
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
}
