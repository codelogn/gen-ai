package com.genai.chatclientjava.exception;

/** Wraps a chat-LLM call failure — mapped to 502, mirroring the Python sibling's HTTPException(502, ...). */
public class ChatLlmException extends RuntimeException {
    public ChatLlmException(String message, Throwable cause) {
        super(message, cause);
    }
}
