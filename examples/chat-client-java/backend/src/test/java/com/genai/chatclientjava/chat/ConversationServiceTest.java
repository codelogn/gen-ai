package com.genai.chatclientjava.chat;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.genai.chatclientjava.domain.Conversation;
import com.genai.chatclientjava.exception.ConversationNotFoundException;
import com.genai.chatclientjava.repository.ConversationRepository;
import com.genai.chatclientjava.repository.MessageRepository;
import com.genai.chatclientjava.repository.UploadRepository;
import java.time.Instant;
import java.util.Optional;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

/**
 * Demonstrates mocking with Mockito: ConversationService's real
 * dependencies (the three repositories) are replaced with fakes we
 * control, so this test never touches a real database — it's testing
 * ConversationService's own logic in isolation.
 */
@ExtendWith(MockitoExtension.class)
class ConversationServiceTest {

    @Mock
    private ConversationRepository conversations;

    @Mock
    private MessageRepository messages;

    @Mock
    private UploadRepository uploads;

    @InjectMocks
    private ConversationService conversationService;

    @Test
    void getOrThrowReturnsTheConversationWhenFound() {
        UUID id = UUID.randomUUID();
        Conversation conversation = new Conversation(id, "Test conversation", Instant.now());
        when(conversations.findById(id)).thenReturn(Optional.of(conversation));

        Conversation result = conversationService.getOrThrow(id);

        assertThat(result).isSameAs(conversation);
    }

    @Test
    void getOrThrowThrowsWhenNotFound() {
        UUID id = UUID.randomUUID();
        when(conversations.findById(id)).thenReturn(Optional.empty());

        assertThatThrownBy(() -> conversationService.getOrThrow(id))
                .isInstanceOf(ConversationNotFoundException.class)
                .hasMessageContaining(id.toString());
    }

    @Test
    void listMessagesChecksTheConversationExistsFirst() {
        UUID id = UUID.randomUUID();
        when(conversations.findById(id)).thenReturn(Optional.empty());

        assertThatThrownBy(() -> conversationService.listMessages(id)).isInstanceOf(ConversationNotFoundException.class);

        // Verifies the repository call actually happened, and that we never
        // even tried to list messages for a conversation that doesn't exist.
        verify(conversations).findById(id);
        verify(messages, never()).findByConversationIdOrderByCreatedAtAsc(any());
    }

    @Test
    void createSavesAndReturnsANewConversation() {
        when(conversations.save(any(Conversation.class))).thenAnswer(invocation -> invocation.getArgument(0));

        Conversation result = conversationService.create("My chat");

        assertThat(result.getTitle()).isEqualTo("My chat");
        assertThat(result.getId()).isNotNull();
    }
}
