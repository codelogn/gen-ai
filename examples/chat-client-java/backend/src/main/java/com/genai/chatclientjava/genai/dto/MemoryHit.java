package com.genai.chatclientjava.genai.dto;

import java.util.Map;

/** One result item from POST /api/v1/memories/search. */
public record MemoryHit(String id, String content, Map<String, Object> metadata, double score, String createdAt) {}
