package com.genai.chatclientjava.genai.dto;

/** Only `id` is actually used (as this client's genaiMemoryId bookkeeping value). */
public record CreateMemoryResponse(String id) {}
