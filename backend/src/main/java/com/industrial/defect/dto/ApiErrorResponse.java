package com.industrial.defect.dto;

import java.time.Instant;

public class ApiErrorResponse {

    private boolean success = false;
    private String error;
    private String message;
    private long timestamp;

    public ApiErrorResponse() {
        this.timestamp = Instant.now().toEpochMilli();
    }

    public ApiErrorResponse(String error, String message) {
        this.success = false;
        this.error = error;
        this.message = message;
        this.timestamp = Instant.now().toEpochMilli();
    }

    public boolean isSuccess() {
        return success;
    }

    public void setSuccess(boolean success) {
        this.success = success;
    }

    public String getError() {
        return error;
    }

    public void setError(String error) {
        this.error = error;
    }

    public String getMessage() {
        return message;
    }

    public void setMessage(String message) {
        this.message = message;
    }

    public long getTimestamp() {
        return timestamp;
    }

    public void setTimestamp(long timestamp) {
        this.timestamp = timestamp;
    }
}
