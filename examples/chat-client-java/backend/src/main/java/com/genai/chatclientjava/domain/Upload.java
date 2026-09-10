package com.genai.chatclientjava.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.time.Instant;
import java.util.UUID;

/**
 * No chunk-content column, same as the Python sibling's uploads table —
 * chunk text lives only in gen-ai; this is filename/count bookkeeping only.
 */
@Entity
@Table(name = "uploads")
public class Upload {

    @Id
    private UUID id;

    @Column(name = "conversation_id", nullable = false)
    private UUID conversationId;

    @Column(nullable = false)
    private String filename;

    @Column(name = "chunk_count", nullable = false)
    private int chunkCount;

    @Column(name = "created_at", nullable = false, updatable = false)
    private Instant createdAt;

    protected Upload() {}

    public Upload(UUID id, UUID conversationId, String filename, int chunkCount, Instant createdAt) {
        this.id = id;
        this.conversationId = conversationId;
        this.filename = filename;
        this.chunkCount = chunkCount;
        this.createdAt = createdAt;
    }

    public UUID getId() {
        return id;
    }

    public UUID getConversationId() {
        return conversationId;
    }

    public String getFilename() {
        return filename;
    }

    public int getChunkCount() {
        return chunkCount;
    }

    public Instant getCreatedAt() {
        return createdAt;
    }
}
