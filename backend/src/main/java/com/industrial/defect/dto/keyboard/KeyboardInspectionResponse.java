package com.industrial.defect.dto.keyboard;

import com.fasterxml.jackson.annotation.JsonAnyGetter;
import com.fasterxml.jackson.annotation.JsonAnySetter;
import java.util.LinkedHashMap;
import java.util.Map;

/** Keyboard contract is intentionally isolated from phone-damage DTOs. */
public class KeyboardInspectionResponse {
    private final Map<String, Object> values = new LinkedHashMap<>();
    @JsonAnyGetter public Map<String, Object> values() { return values; }
    @JsonAnySetter public void put(String name, Object value) { values.put(name, value); }
    public Object get(String name) { return values.get(name); }
}
