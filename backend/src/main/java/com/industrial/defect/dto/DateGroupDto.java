package com.industrial.defect.dto;

import java.time.LocalDate;

public class DateGroupDto {
    private LocalDate date;
    private long sessionCount;
    private long scanCount;
    private long hasDefectCount;

    public DateGroupDto() {
    }

    public DateGroupDto(LocalDate date, long sessionCount, long scanCount, long hasDefectCount) {
        this.date = date;
        this.sessionCount = sessionCount;
        this.scanCount = scanCount;
        this.hasDefectCount = hasDefectCount;
    }

    public LocalDate getDate() {
        return date;
    }

    public void setDate(LocalDate date) {
        this.date = date;
    }

    public long getSessionCount() {
        return sessionCount;
    }

    public void setSessionCount(long sessionCount) {
        this.sessionCount = sessionCount;
    }

    public long getScanCount() {
        return scanCount;
    }

    public void setScanCount(long scanCount) {
        this.scanCount = scanCount;
    }

    public long getHasDefectCount() {
        return hasDefectCount;
    }

    public void setHasDefectCount(long hasDefectCount) {
        this.hasDefectCount = hasDefectCount;
    }
}
