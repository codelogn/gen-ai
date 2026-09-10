package com.genai.chatclientjava.chat.dto;

import com.genai.chatclientjava.domain.Message;
import java.time.Instant;
import java.util.UUID;

public record MessageResponse(
        UUID id, UUID conversationId, String role, String content, String genaiMemoryId, Instant createdAt) {
    public static MessageResponse from(Message m) {
        return new MessageResponse(
                m.getId(),
                m.getConversationId(),
                m.getRole().toWireValue(),
                m.getContent(),
                m.getGenaiMemoryId(),
                m.getCreatedAt());
    }
}
