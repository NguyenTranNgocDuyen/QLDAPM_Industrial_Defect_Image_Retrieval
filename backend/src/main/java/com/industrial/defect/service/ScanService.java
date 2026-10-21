package com.industrial.defect.service;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.industrial.defect.dto.*;
import com.industrial.defect.entity.ScanRecord;
import com.industrial.defect.exception.ResourceNotFoundException;
import com.industrial.defect.repository.ScanRecordRepository;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageImpl;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.multipart.MultipartFile;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.*;

@Service
public class ScanService {
    private final ScanRecordRepository scans;
    private final PythonDamageClient python;
    private final ObjectMapper mapper;

    public ScanService(ScanRecordRepository scans, PythonDamageClient python, ObjectMapper mapper) {
        this.scans = scans;
        this.python = python;
        this.mapper = mapper;
    }

    @Transactional(readOnly = true)
    public DetectionResponseDto getDetectionResult(UUID id) {
        var scan = scans.findByIdWithDetections(id)
                .orElseThrow(() -> new ResourceNotFoundException("Scan not found: " + id));
        if (scan.getAnalysisJson() == null) {
            var result = new DetectionResponseDto();
            result.setScanId(id);
            result.setSuccess(false);
            result.setStatus("insufficient_evidence");
            result.setSeverity(Map.of("status", "insufficient_evidence", "needs_review", true,
                    "reasons", new String[]{"legacy_scan_without_model_evidence"}));
            return result;
        }
        try {
            return mapper.readValue(scan.getAnalysisJson(), DetectionResponseDto.class);
        } catch (JsonProcessingException ex) {
            throw new IllegalStateException("Stored analysis is invalid", ex);
        }
    }

    @Transactional(readOnly = true)
    public Page<ScanSummaryDto> getScanHistory(Boolean hasDefect, Pageable pageable) {
        return getScanHistory(hasDefect, null, pageable);
    }

    @Transactional(readOnly = true)
    public Page<ScanSummaryDto> getScanHistory(Boolean hasDefect, LocalDate date, Pageable pageable) {
        if (date != null) {
            OffsetDateTime start = date.atStartOfDay().atOffset(ZoneOffset.UTC).minusHours(14);
            OffsetDateTime end = date.plusDays(1).atStartOfDay().atOffset(ZoneOffset.UTC).plusHours(14);
            List<ScanRecord> matched = scans.findByCreatedAtBetween(start, end).stream()
                    .filter(s -> s.getCreatedAt() != null && s.getCreatedAt().toLocalDate().equals(date))
                    .filter(s -> hasDefect == null || Objects.equals(s.getHasDefect(), hasDefect))
                    .toList();

            int startIdx = (int) pageable.getOffset();
            int endIdx = Math.min(startIdx + pageable.getPageSize(), matched.size());
            List<ScanSummaryDto> content = startIdx <= endIdx
                    ? matched.subList(startIdx, endIdx).stream().map(this::toScanSummaryDto).toList()
                    : Collections.emptyList();
            return new PageImpl<>(content, pageable, matched.size());
        }

        var page = hasDefect != null ? scans.findByHasDefect(hasDefect, pageable) : scans.findAll(pageable);
        return page.map(this::toScanSummaryDto);
    }

    @Transactional(readOnly = true)
    public List<DateGroupDto> getScanDates() {
        List<ScanRecord> all = scans.findAllOrderByCreatedAtDesc();
        Map<LocalDate, List<ScanRecord>> byDate = new LinkedHashMap<>();
        for (ScanRecord scan : all) {
            if (scan.getCreatedAt() != null) {
                LocalDate d = scan.getCreatedAt().toLocalDate();
                byDate.computeIfAbsent(d, k -> new ArrayList<>()).add(scan);
            }
        }
        List<DateGroupDto> result = new ArrayList<>();
        for (Map.Entry<LocalDate, List<ScanRecord>> entry : byDate.entrySet()) {
            List<InspectionSessionDto> sessions = groupIntoSessions(entry.getValue());
            long scanCount = entry.getValue().size();
            long hasDefectCount = sessions.stream().filter(s -> Boolean.TRUE.equals(s.getHasDefect())).count();
            result.add(new DateGroupDto(entry.getKey(), sessions.size(), scanCount, hasDefectCount));
        }
        return result;
    }

    @Transactional(readOnly = true)
    public List<InspectionSessionDto> getInspectionSessions(LocalDate date) {
        List<ScanRecord> raw;
        if (date != null) {
            OffsetDateTime start = date.atStartOfDay().atOffset(ZoneOffset.UTC).minusHours(14);
            OffsetDateTime end = date.plusDays(1).atStartOfDay().atOffset(ZoneOffset.UTC).plusHours(14);
            raw = scans.findByCreatedAtBetween(start, end).stream()
                    .filter(s -> s.getCreatedAt() != null && s.getCreatedAt().toLocalDate().equals(date))
                    .toList();
        } else {
            raw = scans.findAllOrderByCreatedAtDesc();
        }
        return groupIntoSessions(raw);
    }

    public List<InspectionSessionDto> groupIntoSessions(List<ScanRecord> records) {
        if (records == null || records.isEmpty()) return Collections.emptyList();

        Map<UUID, List<ScanRecord>> explicitSessionGroups = new LinkedHashMap<>();
        List<ScanRecord> unassigned = new ArrayList<>();

        for (ScanRecord record : records) {
            if (record.getSessionId() != null) {
                explicitSessionGroups.computeIfAbsent(record.getSessionId(), k -> new ArrayList<>()).add(record);
            } else {
                unassigned.add(record);
            }
        }

        List<InspectionSessionDto> sessions = new ArrayList<>();

        for (Map.Entry<UUID, List<ScanRecord>> entry : explicitSessionGroups.entrySet()) {
            sessions.add(buildSessionFromRecords(entry.getKey(), entry.getValue()));
        }

        unassigned.sort(Comparator.comparing(ScanRecord::getCreatedAt, Comparator.nullsLast(Comparator.naturalOrder())));

        List<ScanRecord> currentPair = new ArrayList<>();
        for (ScanRecord record : unassigned) {
            if (currentPair.isEmpty()) {
                currentPair.add(record);
            } else {
                ScanRecord first = currentPair.get(0);
                ScanSummaryDto firstDto = toScanSummaryDto(first);
                ScanSummaryDto secondDto = toScanSummaryDto(record);
                boolean differentSurface = firstDto.getSurface() != null && secondDto.getSurface() != null
                        && !firstDto.getSurface().equalsIgnoreCase(secondDto.getSurface());
                long diffSeconds = (first.getCreatedAt() != null && record.getCreatedAt() != null)
                        ? Math.abs(Duration.between(first.getCreatedAt(), record.getCreatedAt()).toSeconds())
                        : Long.MAX_VALUE;

                if (differentSurface && diffSeconds <= 300) {
                    currentPair.add(record);
                    UUID syntheticSessionId = UUID.nameUUIDFromBytes(("session-" + first.getId() + "-" + record.getId()).getBytes(StandardCharsets.UTF_8));
                    sessions.add(buildSessionFromRecords(syntheticSessionId, currentPair));
                    currentPair = new ArrayList<>();
                } else {
                    UUID singleSessionId = UUID.nameUUIDFromBytes(("session-" + first.getId()).getBytes(StandardCharsets.UTF_8));
                    sessions.add(buildSessionFromRecords(singleSessionId, currentPair));
                    currentPair = new ArrayList<>();
                    currentPair.add(record);
                }
            }
        }
        if (!currentPair.isEmpty()) {
            ScanRecord single = currentPair.get(0);
            UUID singleSessionId = UUID.nameUUIDFromBytes(("session-" + single.getId()).getBytes(StandardCharsets.UTF_8));
            sessions.add(buildSessionFromRecords(singleSessionId, currentPair));
        }

        sessions.sort(Comparator.comparing(InspectionSessionDto::getCreatedAt, Comparator.nullsLast(Comparator.reverseOrder())));
        return sessions;
    }

    private InspectionSessionDto buildSessionFromRecords(UUID sessionId, List<ScanRecord> records) {
        InspectionSessionDto session = new InspectionSessionDto();
        session.setSessionId(sessionId);

        ScanSummaryDto front = null;
        ScanSummaryDto back = null;
        List<ScanSummaryDto> others = new ArrayList<>();

        boolean hasDefect = false;
        boolean needsReview = false;
        String highestSeverity = null;
        OffsetDateTime latestTime = null;
        String deviceInfo = null;

        for (ScanRecord r : records) {
            ScanSummaryDto dto = toScanSummaryDto(r);
            dto.setSessionId(sessionId);

            if (deviceInfo == null && r.getDeviceInfo() != null && !r.getDeviceInfo().isBlank()) {
                deviceInfo = r.getDeviceInfo();
            }
            if (latestTime == null || (r.getCreatedAt() != null && r.getCreatedAt().isAfter(latestTime))) {
                latestTime = r.getCreatedAt();
            }
            if (Boolean.TRUE.equals(dto.isHasDefect())) {
                hasDefect = true;
            }
            if (Boolean.TRUE.equals(dto.getNeedsReview())) {
                needsReview = true;
            }
            highestSeverity = compareSeverity(highestSeverity, dto.getEstimatedSeverity());

            String surf = dto.getSurface();
            if ("front".equalsIgnoreCase(surf)) {
                if (front == null) front = dto;
                else others.add(dto);
            } else if ("back".equalsIgnoreCase(surf)) {
                if (back == null) back = dto;
                else others.add(dto);
            } else {
                others.add(dto);
            }
        }

        if (front == null && back != null && !others.isEmpty()) {
            front = others.remove(0);
        } else if (back == null && front != null && !others.isEmpty()) {
            back = others.remove(0);
        } else if (front == null && back == null && !others.isEmpty()) {
            front = others.remove(0);
            if (!others.isEmpty()) {
                back = others.remove(0);
            }
        }

        session.setFrontScan(front);
        session.setBackScan(back);
        session.setOtherScans(others);
        session.setCreatedAt(latestTime);
        session.setDeviceInfo(deviceInfo);
        session.setHasDefect(hasDefect);
        session.setNeedsReview(needsReview);
        session.setOverallSeverity(highestSeverity);
        return session;
    }

    private String compareSeverity(String current, String candidate) {
        if (candidate == null) return current;
        if (current == null) return candidate;
        int rankCurrent = severityRank(current);
        int rankCandidate = severityRank(candidate);
        return rankCandidate >= rankCurrent ? candidate : current;
    }

    private int severityRank(String sev) {
        if ("severe".equalsIgnoreCase(sev)) return 3;
        if ("moderate".equalsIgnoreCase(sev)) return 2;
        if ("minor".equalsIgnoreCase(sev)) return 1;
        return 0;
    }

    public ScanSummaryDto toScanSummaryDto(ScanRecord scan) {
        String surface = null;
        String estimatedSeverity = null;
        Boolean needsReview = null;
        if (scan.getAnalysisJson() != null) {
            try {
                var root = mapper.readTree(scan.getAnalysisJson());
                var damageNode = root.path("damage");
                if (!damageNode.isMissingNode() && damageNode.hasNonNull("observed_surface")) {
                    surface = damageNode.path("observed_surface").asText(null);
                }
                var severityNode = root.path("severity");
                if (!severityNode.isMissingNode()) {
                    if (severityNode.hasNonNull("estimated_severity")) {
                        estimatedSeverity = severityNode.path("estimated_severity").asText(null);
                    }
                    if (severityNode.has("needs_review") && !severityNode.path("needs_review").isNull()) {
                        needsReview = severityNode.path("needs_review").asBoolean();
                    }
                }
            } catch (Exception ignored) {
            }
        }
        var dto = new ScanSummaryDto(
                scan.getId(),
                scan.getOriginalFilename(),
                scan.getDisplayImageUrl(),
                scan.getAnalysisJson() == null ? null : scan.getHasDefect(),
                scan.getDetections().size(),
                scan.getAnalysisJson() == null ? "insufficient_evidence" : scan.getStatus(),
                scan.getTotalMs(),
                scan.getCreatedAt()
        );
        dto.setSessionId(scan.getSessionId());
        dto.setSourceImageUrl(scan.getSourceImageUrl());
        dto.setSurface(surface);
        dto.setEstimatedSeverity(estimatedSeverity);
        dto.setNeedsReview(needsReview);
        return dto;
    }

    @Transactional
    public DetectionResponseDto processImageUpload(MultipartFile file, String deviceInfo,
                                                   String surface, Double aspect, boolean complete) {
        return processImageUpload(file, deviceInfo, surface, aspect, complete, null);
    }

    @Transactional
    public DetectionResponseDto processImageUpload(MultipartFile file, String deviceInfo,
                                                   String surface, Double aspect, boolean complete, UUID sessionId) {
        if (file.isEmpty()) throw new IllegalArgumentException("Uploaded image cannot be empty");
        if (aspect != null && (!Double.isFinite(aspect) || aspect < 0.1 || aspect > 10)) {
            throw new IllegalArgumentException("Surface width/height ratio must be between 0.1 and 10");
        }
        DetectionResponseDto result;
        try {
            result = python.analyze(file.getBytes(), surface, aspect, complete);
        } catch (IOException ex) {
            throw new IllegalArgumentException("Cannot read uploaded image", ex);
        }
        var scan = new ScanRecord();
        scan.setSessionId(sessionId);
        scan.setOriginalFilename(file.getOriginalFilename());
        scan.setDeviceInfo(deviceInfo);
        scan.setSourceImageUrl(result.getSourceImage().getUrl());
        scan.setSourceWidth(result.getSourceImage().getWidth());
        scan.setSourceHeight(result.getSourceImage().getHeight());
        scan.setDisplayImageUrl(result.getDisplayImage().getUrl());
        scan.setDisplayWidth(result.getDisplayImage().getWidth());
        scan.setDisplayHeight(result.getDisplayImage().getHeight());
        scan.setCoordinateSpace(result.getDisplayImage().getCoordinateSpace());
        scan.setSuccess(result.isSuccess());
        scan.setHasDefect(result.isHasDefect());
        scan.setStatus(result.getStatus());
        scan.setPreprocessingMs(result.getProcessing().getPreprocessingMs());
        scan.setInferenceMs(result.getProcessing().getInferenceMs());
        scan.setPostprocessingMs(result.getProcessing().getPostprocessingMs());
        scan.setTotalMs(result.getProcessing().getTotalMs());
        scan = scans.save(scan);
        result.setScanId(scan.getId());
        try {
            scan.setAnalysisJson(mapper.writeValueAsString(result));
        } catch (JsonProcessingException ex) {
            throw new IllegalStateException("Cannot store analysis", ex);
        }
        return result;
    }
}
