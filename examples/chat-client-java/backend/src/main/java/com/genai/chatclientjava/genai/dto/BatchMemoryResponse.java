package com.genai.chatclientjava.genai.dto;

import java.util.List;

/** Only the counts are used — `failed` items' shape ({index, error}) isn't needed here. */
public record BatchMemoryResponse(List<String> created, List<Object> failed) {}
