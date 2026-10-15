# =============================================================================
# Multi-stage Dockerfile for Spring Boot Backend
# =============================================================================
FROM eclipse-temurin:21-jdk-alpine AS builder

WORKDIR /workspace

COPY pom.xml .
COPY src ./src

RUN ./mvnw clean package -DskipTests 2>/dev/null || mvn clean package -DskipTests

# Runtime Stage
FROM eclipse-temurin:21-jre-alpine

WORKDIR /app

COPY --from=builder /workspace/target/*.jar app.jar

EXPOSE 8080

ENTRYPOINT ["java", "-jar", "app.jar"]
