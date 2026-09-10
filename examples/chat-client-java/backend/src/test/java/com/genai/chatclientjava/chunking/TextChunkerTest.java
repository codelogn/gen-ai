package com.genai.chatclientjava.chunking;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.List;
import org.junit.jupiter.api.Test;

class TextChunkerTest {

    @Test
    void blankInputReturnsNoChunks() {
        assertThat(TextChunker.chunk("   ", 500, 50)).isEmpty();
    }

    @Test
    void textShorterThanChunkSizeReturnsAsOneChunk() {
        assertThat(TextChunker.chunk("hello world", 500, 50)).containsExactly("hello world");
    }

    @Test
    void textLongerThanChunkSizeSplitsWithOverlap() {
        String text = "0123456789abcdefghij"; // 20 chars

        List<String> chunks = TextChunker.chunk(text, 10, 2);

        assertThat(chunks).containsExactly("0123456789", "89abcdefgh", "ghij");
    }

    @Test
    void trimsWhitespaceFromEachChunk() {
        assertThat(TextChunker.chunk("  hello world  ", 500, 50)).containsExactly("hello world");
    }
}
