package com.genai.chatclientjava.genai.dto;

/** POST /api/v1/memories/search request body. namespace is required, subjectId is not. */
public record SearchRequest(String namespace, String subjectId, String query, int topK) {}
