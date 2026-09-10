package com.genai.chatclientjava.chat;

import com.genai.chatclientjava.domain.Conversation;
import com.genai.chatclientjava.domain.Message;
import com.genai.chatclientjava.domain.Upload;
import com.genai.chatclientjava.exception.ConversationNotFoundException;
import com.genai.chatclientjava.repository.ConversationRepository;
import com.genai.chatclientjava.repository.MessageRepository;
import com.genai.chatclientjava.repository.UploadRepository;
import java.time.Instant;
import java.util.List;
import java.util.UUID;
import org.springframework.stereotype.Service;

@Service
public class ConversationService {

    private final ConversationRepository conversations;
    private final MessageRepository messages;
    private final UploadRepository uploads;

    public ConversationService(ConversationRepository conversations, MessageRepository messages, UploadRepository uploads) {
        this.conversations = conversations;
        this.messages = messages;
        this.uploads = uploads;
    }

    public Conversation create(String title) {
        Conversation conversation = new Conversation(UUID.randomUUID(), title, Instant.now());
        return conversations.save(conversation);
    }

    public List<Conversation> list() {
        return conversations.findAllByOrderByCreatedAtDesc();
    }

    public Conversation getOrThrow(UUID conversationId) {
        return conversations.findById(conversationId).orElseThrow(() -> new ConversationNotFoundException(conversationId));
    }

    public List<Message> listMessages(UUID conversationId) {
        getOrThrow(conversationId);
        return messages.findByConversationIdOrderByCreatedAtAsc(conversationId);
    }

    public List<Upload> listUploads(UUID conversationId) {
        getOrThrow(conversationId);
        return uploads.findByConversationIdOrderByCreatedAtDesc(conversationId);
    }
}
