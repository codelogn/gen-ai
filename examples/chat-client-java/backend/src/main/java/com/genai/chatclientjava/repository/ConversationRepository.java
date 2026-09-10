package com.genai.chatclientjava.repository;

import com.genai.chatclientjava.domain.Conversation;
import java.util.List;
import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;

public interface ConversationRepository extends JpaRepository<Conversation, UUID> {
    List<Conversation> findAllByOrderByCreatedAtDesc();
}
