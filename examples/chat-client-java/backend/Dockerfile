FROM maven:3.9-eclipse-temurin-21 AS build
WORKDIR /build
COPY pom.xml .
RUN mvn -B dependency:go-offline
COPY src/ ./src/
RUN mvn -B package -DskipTests

FROM eclipse-temurin:21-jre-alpine
WORKDIR /app
COPY --from=build /build/target/*.jar app.jar
# Under network_mode: host (see ../docker-compose.yml), this EXPOSE is
# documentation only — the actual bound port is server.port (SERVER_PORT env).
EXPOSE 9001
ENTRYPOINT ["java", "-jar", "app.jar"]
