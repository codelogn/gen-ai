package com.genai.chatclientjava.domain;

public enum MessageRole {
    USER,
    ASSISTANT;

    /** gen-ai metadata and the JSON API use lowercase role strings. */
    public String toWireValue() {
        return name().toLowerCase();
    }
}
