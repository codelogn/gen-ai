package com.genai.chatclientjava.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.time.Instant;
import java.util.UUID;

/**
 * content IS duplicated here, deliberately — same choice the Python
 * sibling's db.py makes (see its own comment): a local copy for fast,
 * ordered recency-window rendering, but gen-ai's copy (referenced via
 * genaiMemoryId) remains the canonical, long-term-searchable one.
 */
@Entity
@Table(name = "messages")
public class Message {

    @Id
    private UUID id;

    @Column(name = "conversation_id", nullable = false)
    private UUID conversationId;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    private MessageRole role;

    @Column(nullable = false, columnDefinition = "text")
    private String content;

    @Column(name = "genai_memory_id")
    private String genaiMemoryId;

    @Column(name = "created_at", nullable = false, updatable = false)
    private Instant createdAt;

    protected Message() {}

    public Message(
            UUID id, UUID conversationId, MessageRole role, String content, String genaiMemoryId, Instant createdAt) {
        this.id = id;
        this.conversationId = conversationId;
        this.role = role;
        this.content = content;
        this.genaiMemoryId = genaiMemoryId;
        this.createdAt = createdAt;
    }

    public UUID getId() {
        return id;
    }

    public UUID getConversationId() {
        return conversationId;
    }

    public MessageRole getRole() {
        return role;
    }

    public String getContent() {
        return content;
    }

    public String getGenaiMemoryId() {
        return genaiMemoryId;
    }

    public Instant getCreatedAt() {
        return createdAt;
    }
}
