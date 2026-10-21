package com.industrial.defect;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIf;
import org.springframework.boot.test.context.SpringBootTest;

import java.net.InetSocketAddress;
import java.net.Socket;
import java.net.URI;

@SpringBootTest
@EnabledIf("isDatabaseRunning")
class DefectInspectionApplicationTests {

    static boolean isDatabaseRunning() {
        String url = System.getenv("SPRING_DATASOURCE_URL");
        String host = "localhost";
        int port = 5433;
        if (url != null && url.startsWith("jdbc:postgresql://")) {
            try {
                URI cleanUri = URI.create(url.substring(5)); // remove "jdbc:"
                if (cleanUri.getHost() != null) host = cleanUri.getHost();
                if (cleanUri.getPort() != -1) port = cleanUri.getPort();
            } catch (Exception ignored) {
            }
        }
        try (Socket socket = new Socket()) {
            socket.connect(new InetSocketAddress(host, port), 500);
            return true;
        } catch (Exception e) {
            return false;
        }
    }

    @Test
    void contextLoads() {
    }
}

