package com.industrial.defect.dto;

public class ProcessingTimingDto {

    private double preprocessingMs;
    private double inferenceMs;
    private double postprocessingMs;
    private double totalMs;

    public ProcessingTimingDto() {
    }

    public ProcessingTimingDto(double preprocessingMs, double inferenceMs, double postprocessingMs, double totalMs) {
        this.preprocessingMs = preprocessingMs;
        this.inferenceMs = inferenceMs;
        this.postprocessingMs = postprocessingMs;
        this.totalMs = totalMs;
    }

    public double getPreprocessingMs() {
        return preprocessingMs;
    }

    public void setPreprocessingMs(double preprocessingMs) {
        this.preprocessingMs = preprocessingMs;
    }

    public double getInferenceMs() {
        return inferenceMs;
    }

    public void setInferenceMs(double inferenceMs) {
        this.inferenceMs = inferenceMs;
    }

    public double getPostprocessingMs() {
        return postprocessingMs;
    }

    public void setPostprocessingMs(double postprocessingMs) {
        this.postprocessingMs = postprocessingMs;
    }

    public double getTotalMs() {
        return totalMs;
    }

    public void setTotalMs(double totalMs) {
        this.totalMs = totalMs;
    }
}
