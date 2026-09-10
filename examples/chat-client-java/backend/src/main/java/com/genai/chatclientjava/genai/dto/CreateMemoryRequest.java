package com.genai.chatclientjava.genai.dto;

import java.util.Map;

/** POST /api/v1/memories request body — see docs/08-api-reference.md. */
public record CreateMemoryRequest(String namespace, String subjectId, String content, Map<String, Object> metadata) {}
