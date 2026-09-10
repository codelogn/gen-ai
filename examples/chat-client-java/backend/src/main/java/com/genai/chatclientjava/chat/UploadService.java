package com.genai.chatclientjava.chat;

import com.genai.chatclientjava.chat.dto.UploadResultResponse;
import com.genai.chatclientjava.chunking.TextChunker;
import com.genai.chatclientjava.config.ChatClientProperties;
import com.genai.chatclientjava.domain.Upload;
import com.genai.chatclientjava.genai.GenAiClient;
import com.genai.chatclientjava.genai.dto.BatchMemoryItem;
import com.genai.chatclientjava.repository.UploadRepository;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.UUID;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;

/**
 * The upload -> chunk -> embed path — mirrors
 * examples/chat-client-python/backend/app/main.py::upload_document. Only
 * .txt/.md files, only bookkeeping (filename + chunk count) stored
 * locally; the actual chunk text lives entirely in gen-ai.
 */
@Service
public class UploadService {

    private static final String DOCUMENTS_NAMESPACE = "documents";

    private final GenAiClient genAi;
    private final UploadRepository uploads;
    private final ConversationService conversationService;
    private final ChatClientProperties props;

    public UploadService(
            GenAiClient genAi, UploadRepository uploads, ConversationService conversationService, ChatClientProperties props) {
        this.genAi = genAi;
        this.uploads = uploads;
        this.conversationService = conversationService;
        this.props = props;
    }

    public UploadResultResponse upload(UUID conversationId, MultipartFile file) {
        conversationService.getOrThrow(conversationId);

        String filename = file.getOriginalFilename() == null ? "upload" : file.getOriginalFilename();
        String lower = filename.toLowerCase(Locale.ROOT);
        if (!(lower.endsWith(".txt") || lower.endsWith(".md"))) {
            throw new IllegalArgumentException("Only .txt and .md files are supported");
        }

        String raw = readAsUtf8(file);
        List<String> chunks = TextChunker.chunk(raw, props.chunkSizeChars(), props.chunkOverlapChars());
        if (chunks.isEmpty()) {
            throw new IllegalArgumentException("File is empty");
        }

        List<BatchMemoryItem> items = new ArrayList<>();
        for (int i = 0; i < chunks.size(); i++) {
            items.add(new BatchMemoryItem(
                    DOCUMENTS_NAMESPACE,
                    conversationId.toString(),
                    chunks.get(i),
                    Map.of("filename", filename, "chunk_index", i)));
        }
        var result = genAi.createMemoriesBatch(items);

        uploads.save(new Upload(UUID.randomUUID(), conversationId, filename, result.created().size(), Instant.now()));

        return new UploadResultResponse(filename, result.created().size(), result.failed().size());
    }

    private String readAsUtf8(MultipartFile file) {
        try {
            // Java's String(byte[], Charset) already replaces malformed
            // sequences with U+FFFD by default, matching Python's
            // decode("utf-8", errors="replace").
            return new String(file.getBytes(), StandardCharsets.UTF_8);
        } catch (IOException e) {
            throw new IllegalArgumentException("Could not read uploaded file: " + e.getMessage());
        }
    }
}
