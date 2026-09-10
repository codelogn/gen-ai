package com.genai.chatclientjava.repository;

import com.genai.chatclientjava.domain.Upload;
import java.util.List;
import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;

public interface UploadRepository extends JpaRepository<Upload, UUID> {
    List<Upload> findByConversationIdOrderByCreatedAtDesc(UUID conversationId);
}
