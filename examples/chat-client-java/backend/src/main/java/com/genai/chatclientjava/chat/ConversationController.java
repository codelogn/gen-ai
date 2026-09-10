package com.genai.chatclientjava.chat;

import com.genai.chatclientjava.chat.dto.ConversationResponse;
import com.genai.chatclientjava.chat.dto.CreateConversationRequest;
import com.genai.chatclientjava.chat.dto.CreateConversationResponse;
import com.genai.chatclientjava.chat.dto.MessageResponse;
import com.genai.chatclientjava.chat.dto.UploadResponse;
import java.util.List;
import java.util.UUID;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class ConversationController {

    private final ConversationService conversationService;

    public ConversationController(ConversationService conversationService) {
        this.conversationService = conversationService;
    }

    @PostMapping("/conversations")
    public CreateConversationResponse create(@RequestBody(required = false) CreateConversationRequest request) {
        String title = request == null ? null : request.title();
        return new CreateConversationResponse(conversationService.create(title).getId());
    }

    @GetMapping("/conversations")
    public List<ConversationResponse> list() {
        return conversationService.list().stream().map(ConversationResponse::from).toList();
    }

    @GetMapping("/conversations/{conversationId}/messages")
    public List<MessageResponse> messages(@PathVariable UUID conversationId) {
        return conversationService.listMessages(conversationId).stream().map(MessageResponse::from).toList();
    }

    @GetMapping("/conversations/{conversationId}/uploads")
    public List<UploadResponse> uploads(@PathVariable UUID conversationId) {
        return conversationService.listUploads(conversationId).stream().map(UploadResponse::from).toList();
    }
}
