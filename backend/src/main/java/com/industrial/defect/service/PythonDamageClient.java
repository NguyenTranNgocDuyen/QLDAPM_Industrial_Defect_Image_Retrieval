package com.industrial.defect.service;

import com.industrial.defect.dto.DetectionResponseDto;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.MediaType;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

@Component
public class PythonDamageClient {
    private final RestClient client;
    public PythonDamageClient(@Value("${python.service.url}") String url,
                              @Value("${python.service.connect-timeout-ms:5000}") int connectTimeout,
                              @Value("${python.service.read-timeout-ms:300000}") int readTimeout) {
        var factory = new SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(connectTimeout);
        factory.setReadTimeout(readTimeout);
        client = RestClient.builder().baseUrl(url).requestFactory(factory).build();
    }
    public DetectionResponseDto analyze(byte[] image, String surface, Double aspect, boolean complete) {
        var response = client.post().uri(builder -> {
            builder.path("/analyze").queryParam("surface", surface).queryParam("complete", complete);
            if (aspect != null) builder.queryParam("aspect", aspect);
            return builder.build();
        }).contentType(MediaType.APPLICATION_OCTET_STREAM).body(image).retrieve().body(DetectionResponseDto.class);
        if (response == null || response.getDamage() == null || response.getSeverity() == null
                || response.getSourceImage() == null || response.getDisplayImage() == null) {
            throw new IllegalStateException("Python worker returned incomplete evidence.");
        }
        return response;
    }
    public byte[] asset(String scanId, String filename) {
        return client.get().uri("/api/damage-assets/{id}/{filename}", scanId, filename)
                .retrieve().body(byte[].class);
    }
}
