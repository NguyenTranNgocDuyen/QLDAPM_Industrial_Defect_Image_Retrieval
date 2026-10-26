package com.industrial.defect.controller;

import com.industrial.defect.service.PythonDamageClient;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import java.util.UUID;

@RestController
@RequestMapping("/api/damage-assets")
public class DamageAssetController {
    private final PythonDamageClient client;
    public DamageAssetController(PythonDamageClient client) { this.client = client; }
    @GetMapping("/{id}/{filename}")
    public ResponseEntity<byte[]> image(@PathVariable UUID id, @PathVariable String filename) {
        if (!filename.matches("[a-z_]+\\.png")) throw new IllegalArgumentException("Invalid PNG asset name");
        return ResponseEntity.ok().contentType(MediaType.IMAGE_PNG).body(client.asset(id.toString(), filename));
    }
}
