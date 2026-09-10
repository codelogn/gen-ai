package com.genai.chatclientjava.chunking;

import java.util.ArrayList;
import java.util.List;

/**
 * Fixed-size chunking with overlap — a literal port of
 * examples/chat-client-python/backend/app/chunking.py::chunk_text, same
 * algorithm and edge cases. Chunking is correctly an ingestion-side
 * (client) concern, not something gen-ai imposes — see docs/03-memory-data-model.md.
 */
public final class TextChunker {

    private TextChunker() {}

    public static List<String> chunk(String text, int chunkSize, int overlap) {
        String trimmed = text.strip();
        if (trimmed.isEmpty()) {
            return List.of();
        }
        if (trimmed.length() <= chunkSize) {
            return List.of(trimmed);
        }

        List<String> chunks = new ArrayList<>();
        int start = 0;
        while (start < trimmed.length()) {
            // Python's text[start:end] with an out-of-range end just returns
            // to end-of-string; Math.min reproduces that safely here, where
            // substring() would otherwise throw.
            int end = Math.min(start + chunkSize, trimmed.length());
            String piece = trimmed.substring(start, end).strip();
            if (!piece.isEmpty()) {
                chunks.add(piece);
            }
            if (end >= trimmed.length()) {
                break;
            }
            start = end - overlap;
        }
        return chunks;
    }
}
