package com.genai.chatclientjava.chat.dto;

import com.genai.chatclientjava.domain.Upload;
import java.time.Instant;
import java.util.UUID;

public record UploadResponse(UUID id, UUID conversationId, String filename, int chunkCount, Instant createdAt) {
    public static UploadResponse from(Upload u) {
        return new UploadResponse(u.getId(), u.getConversationId(), u.getFilename(), u.getChunkCount(), u.getCreatedAt());
    }
}
