package com.genai.chatclientjava.chat;

import com.genai.chatclientjava.chat.dto.SendMessageRequest;
import com.genai.chatclientjava.chat.dto.SendMessageResponse;
import jakarta.validation.Valid;
import java.util.UUID;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class ChatController {

    private final RagChatService ragChatService;

    public ChatController(RagChatService ragChatService) {
        this.ragChatService = ragChatService;
    }

    @PostMapping("/conversations/{conversationId}/messages")
    public SendMessageResponse sendMessage(@PathVariable UUID conversationId, @Valid @RequestBody SendMessageRequest request) {
        return ragChatService.sendMessage(conversationId, request.content());
    }
}
