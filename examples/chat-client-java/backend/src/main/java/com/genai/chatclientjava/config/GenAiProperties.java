package com.genai.chatclientjava.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "genai")
public record GenAiProperties(String apiUrl, String apiKey) {}
