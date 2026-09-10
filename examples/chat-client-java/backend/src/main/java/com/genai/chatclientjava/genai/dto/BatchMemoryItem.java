package com.genai.chatclientjava.genai.dto;

import java.util.Map;

public record BatchMemoryItem(String namespace, String subjectId, String content, Map<String, Object> metadata) {}
