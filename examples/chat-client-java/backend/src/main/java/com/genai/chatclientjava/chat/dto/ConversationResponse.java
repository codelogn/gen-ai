package com.genai.chatclientjava.chat.dto;

import com.genai.chatclientjava.domain.Conversation;
import java.time.Instant;
import java.util.UUID;

public record ConversationResponse(UUID id, String title, Instant createdAt) {
    public static ConversationResponse from(Conversation c) {
        return new ConversationResponse(c.getId(), c.getTitle(), c.getCreatedAt());
    }
}
