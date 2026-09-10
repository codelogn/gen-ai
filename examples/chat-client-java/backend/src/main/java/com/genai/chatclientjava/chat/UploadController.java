package com.genai.chatclientjava.chat;

import com.genai.chatclientjava.chat.dto.UploadResultResponse;
import java.util.UUID;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

@RestController
public class UploadController {

    private final UploadService uploadService;

    public UploadController(UploadService uploadService) {
        this.uploadService = uploadService;
    }

    @PostMapping("/conversations/{conversationId}/upload")
    public UploadResultResponse upload(@PathVariable UUID conversationId, @RequestParam("file") MultipartFile file) {
        return uploadService.upload(conversationId, file);
    }
}
