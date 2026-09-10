package com.genai.chatclientjava.chat;

import com.genai.chatclientjava.chat.dto.SendMessageResponse;
import com.genai.chatclientjava.config.ChatClientProperties;
import com.genai.chatclientjava.domain.Conversation;
import com.genai.chatclientjava.domain.Message;
import com.genai.chatclientjava.domain.MessageRole;
import com.genai.chatclientjava.exception.ChatLlmException;
import com.genai.chatclientjava.exception.ConversationNotFoundException;
import com.genai.chatclientjava.genai.GenAiClient;
import com.genai.chatclientjava.genai.dto.MemoryHit;
import com.genai.chatclientjava.repository.ConversationRepository;
import com.genai.chatclientjava.repository.MessageRepository;
import java.time.Instant;
import java.util.Collections;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.springframework.ai.chat.client.ChatClient;
import org.springframework.data.domain.PageRequest;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * A literal 5-step port of examples/chat-client-python/backend/app/main.py's
 * send_message: persist user message (gen-ai then local) -> build context
 * (recency window + two independent semantic searches) -> generate a reply
 * -> persist the reply the same dual way. This is the actual RAG loop.
 */
@Service
public class RagChatService {

    private static final String MESSAGES_NAMESPACE = "messages";
    private static final String DOCUMENTS_NAMESPACE = "documents";
    private static final int TITLE_MAX_LENGTH = 80;

    private final ConversationRepository conversations;
    private final MessageRepository messages;
    private final GenAiClient genAi;
    private final ChatClient chatClient;
    private final ChatClientProperties props;
    private final SystemPromptBuilder promptBuilder;

    public RagChatService(
            ConversationRepository conversations,
            MessageRepository messages,
            GenAiClient genAi,
            ChatClient chatClient,
            ChatClientProperties props,
            SystemPromptBuilder promptBuilder) {
        this.conversations = conversations;
        this.messages = messages;
        this.genAi = genAi;
        this.chatClient = chatClient;
        this.props = props;
        this.promptBuilder = promptBuilder;
    }

    @Transactional
    public SendMessageResponse sendMessage(UUID conversationId, String rawContent) {
        Conversation conversation = conversations
                .findById(conversationId)
                .orElseThrow(() -> new ConversationNotFoundException(conversationId));

        String userMessage = rawContent.strip();
        if (userMessage.isEmpty()) {
            throw new IllegalArgumentException("content cannot be empty");
        }

        // 1. Persist the user's message — gen-ai first (need its memory id
        //    for local bookkeeping), then locally (fast, ordered, for UI
        //    rendering + recency window).
        var genaiMsg = genAi.createMemory(
                MESSAGES_NAMESPACE, userMessage, conversationId.toString(), Map.of("role", "user"));
        messages.save(newMessage(conversationId, MessageRole.USER, userMessage, genaiMsg.id()));
        setTitleIfUnset(conversation, userMessage);

        // 2. Build context: recency window (local) + semantic search across
        //    both namespaces (gen-ai) — this is the actual RAG loop.
        List<Message> recent = recentMessages(conversationId);
        List<MemoryHit> messageHits = genAi.search(
                MESSAGES_NAMESPACE, userMessage, conversationId.toString(), props.semanticSearchTopK());
        List<MemoryHit> documentHits = genAi.search(
                DOCUMENTS_NAMESPACE, userMessage, conversationId.toString(), props.semanticSearchTopK());

        String systemPrompt = promptBuilder.build(recent, messageHits, documentHits);

        // 3. Generate the reply.
        String reply;
        try {
            reply = chatClient.prompt().system(systemPrompt).user(userMessage).call().content();
        } catch (Exception e) {
            throw new ChatLlmException("Chat LLM call failed: " + e.getMessage(), e);
        }

        // 4. Persist the assistant's reply the same dual way as step 1.
        var genaiReply = genAi.createMemory(
                MESSAGES_NAMESPACE, reply, conversationId.toString(), Map.of("role", "assistant"));
        messages.save(newMessage(conversationId, MessageRole.ASSISTANT, reply, genaiReply.id()));

        return new SendMessageResponse("assistant", reply);
    }

    private List<Message> recentMessages(UUID conversationId) {
        // findByConversationIdOrderByCreatedAtDesc + reverse gives chronological
        // order, mirroring db.py's get_recent_messages(): reversed(rows).
        List<Message> descending = messages.findByConversationIdOrderByCreatedAtDesc(
                conversationId, PageRequest.of(0, props.recentMessagesWindow()));
        Collections.reverse(descending);
        return descending;
    }

    private void setTitleIfUnset(Conversation conversation, String title) {
        if (conversation.getTitle() == null || conversation.getTitle().isBlank()) {
            conversation.setTitle(title.length() > TITLE_MAX_LENGTH ? title.substring(0, TITLE_MAX_LENGTH) : title);
            conversations.save(conversation);
        }
    }

    private Message newMessage(UUID conversationId, MessageRole role, String content, String genaiMemoryId) {
        return new Message(UUID.randomUUID(), conversationId, role, content, genaiMemoryId, Instant.now());
    }
}
