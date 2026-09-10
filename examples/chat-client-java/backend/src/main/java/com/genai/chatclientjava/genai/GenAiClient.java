package com.genai.chatclientjava.genai;

import com.genai.chatclientjava.config.GenAiProperties;
import com.genai.chatclientjava.genai.dto.BatchMemoryItem;
import com.genai.chatclientjava.genai.dto.BatchMemoryRequest;
import com.genai.chatclientjava.genai.dto.BatchMemoryResponse;
import com.genai.chatclientjava.genai.dto.CreateMemoryRequest;
import com.genai.chatclientjava.genai.dto.CreateMemoryResponse;
import com.genai.chatclientjava.genai.dto.MemoryHit;
import com.genai.chatclientjava.genai.dto.SearchRequest;
import com.genai.chatclientjava.genai.dto.SearchResponse;
import java.net.http.HttpClient;
import java.util.List;
import java.util.Map;
import org.springframework.http.client.JdkClientHttpRequestFactory;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

/**
 * Thin wrapper over gen-ai's REST API — this is the ENTIRE integration
 * surface, mirroring examples/chat-client-python/backend/app/genai_client.py
 * method for method. No gen-ai internals are imported or assumed; this
 * talks to it exactly the way any other REST client would, using nothing
 * but the public contract in docs/08-api-reference.md.
 */
@Component
public class GenAiClient {

    private final RestClient restClient;

    // Builder is INJECTED (Spring Boot's auto-configured RestClient.Builder
    // bean), never RestClient.builder() called directly — that static
    // factory builds its own default Jackson ObjectMapper that knows
    // nothing about spring.jackson.property-naming-strategy: SNAKE_CASE
    // (application.yml). Got bitten by this for real: subject_id came
    // back as null on every memory this client wrote, because "subjectId"
    // was being serialized literally instead of as "subject_id" — the
    // injected builder carries the app's actual configured ObjectMapper,
    // fixing it for every DTO field, not just this one.
    public GenAiClient(RestClient.Builder builder, GenAiProperties props) {
        // The JDK's built-in java.net.http.HttpClient (RestClient's default
        // backing client) probes for an HTTP/2 cleartext (h2c) upgrade by
        // default — uvicorn (gen-ai's server) doesn't support that upgrade
        // and rejects the probe outright ("Unsupported upgrade request" /
        // "Invalid HTTP request received" in gen-ai's own logs), which
        // surfaces here as a bogus 400 before any real request is even
        // processed. Pinning HTTP/1.1 explicitly avoids the probe entirely.
        // Found by actually running this against gen-ai, not by inspection.
        HttpClient httpClient = HttpClient.newBuilder()
                .version(HttpClient.Version.HTTP_1_1)
                .build();
        this.restClient = builder
                .baseUrl(props.apiUrl())
                .requestFactory(new JdkClientHttpRequestFactory(httpClient))
                .defaultHeader("X-API-Key", props.apiKey())
                .defaultHeader("Content-Type", "application/json")
                .build();
    }

    public CreateMemoryResponse createMemory(
            String namespace, String content, String subjectId, Map<String, Object> metadata) {
        return restClient
                .post()
                .uri("/api/v1/memories")
                .body(new CreateMemoryRequest(namespace, subjectId, content, metadata))
                .retrieve()
                .body(CreateMemoryResponse.class);
    }

    public BatchMemoryResponse createMemoriesBatch(List<BatchMemoryItem> items) {
        return restClient
                .post()
                .uri("/api/v1/memories/batch")
                .body(new BatchMemoryRequest(items))
                .retrieve()
                .body(BatchMemoryResponse.class);
    }

    public List<MemoryHit> search(String namespace, String query, String subjectId, int topK) {
        SearchResponse response = restClient
                .post()
                .uri("/api/v1/memories/search")
                .body(new SearchRequest(namespace, subjectId, query, topK))
                .retrieve()
                .body(SearchResponse.class);
        return response == null ? List.of() : response.results();
    }
}
