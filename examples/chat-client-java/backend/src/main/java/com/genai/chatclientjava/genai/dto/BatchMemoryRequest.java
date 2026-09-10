package com.genai.chatclientjava.genai.dto;

import java.util.List;

/** POST /api/v1/memories/batch request body. */
public record BatchMemoryRequest(List<BatchMemoryItem> items) {}
