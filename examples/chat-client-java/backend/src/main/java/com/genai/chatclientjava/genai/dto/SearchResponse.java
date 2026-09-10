package com.genai.chatclientjava.genai.dto;

import java.util.List;

public record SearchResponse(List<MemoryHit> results) {}
