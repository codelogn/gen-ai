package com.genai.chatclientjava.repository;

import com.genai.chatclientjava.domain.Message;
import java.util.List;
import java.util.UUID;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;

public interface MessageRepository extends JpaRepository<Message, UUID> {

    List<Message> findByConversationIdOrderByCreatedAtAsc(UUID conversationId);

    // The recency window size (RECENT_MESSAGES_WINDOW) is runtime-configurable,
    // not a compile-time constant, so a Pageable-limited query is used instead
    // of a findTopN-style derived query. Caller reverses the result to get
    // chronological order — mirrors db.py's get_recent_messages() exactly.
    List<Message> findByConversationIdOrderByCreatedAtDesc(UUID conversationId, Pageable pageable);
}
