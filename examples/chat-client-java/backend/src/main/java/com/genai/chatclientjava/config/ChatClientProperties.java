package com.genai.chatclientjava.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

/**
 * Mirrors the Python client's own env-configurable knobs (CHAT_LLM_PROVIDER,
 * RECENT_MESSAGES_WINDOW, SEMANTIC_SEARCH_TOP_K, CHUNK_SIZE_CHARS,
 * CHUNK_OVERLAP_CHARS) 1:1 — see examples/chat-client-python/backend/app/config.py.
 */
@ConfigurationProperties(prefix = "chat-client")
public record ChatClientProperties(
        String provider,
        String model,
        int recentMessagesWindow,
        int semanticSearchTopK,
        int chunkSizeChars,
        int chunkOverlapChars) {}
