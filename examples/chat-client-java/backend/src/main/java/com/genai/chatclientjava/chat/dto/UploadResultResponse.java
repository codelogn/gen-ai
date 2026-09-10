package com.genai.chatclientjava.chat.dto;

public record UploadResultResponse(String filename, int chunksCreated, int chunksFailed) {}
