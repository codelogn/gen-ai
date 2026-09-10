package com.genai.chatclientjava.config;

import org.springframework.ai.chat.client.ChatClient;
import org.springframework.ai.chat.model.ChatModel;
import org.springframework.ai.ollama.OllamaChatModel;
import org.springframework.ai.openai.OpenAiChatModel;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * The one place that branches on chat-client.provider — the Java analog
 * of the if/elif provider dispatch in the Python sibling's chat_llm.py,
 * done once at bean-construction time rather than per request. Both
 * OllamaChatModel and OpenAiChatModel are auto-configured unconditionally
 * (both Spring AI starters are on the classpath — see pom.xml); we just
 * pick one and build a single ChatClient from it. Spring AI normalizes
 * both providers' very different wire formats behind one
 * chatClient.prompt()...call().content() call — no manual response-shape
 * parsing needed, unlike the Python version.
 *
 * Note: OpenAiChatModel's autoconfiguration validates its API key
 * EAGERLY at context startup (not lazily at call time) — see the
 * spring.ai.openai.api-key placeholder default in application.yml, which
 * exists purely so this bean can construct under provider=ollama with no
 * real OpenAI key configured.
 */
@Configuration
public class ChatClientConfig {

    @Bean
    public ChatClient chatClient(
            ChatClientProperties props, OllamaChatModel ollamaChatModel, OpenAiChatModel openAiChatModel) {
        ChatModel selected =
                switch (props.provider()) {
                    case "ollama" -> ollamaChatModel;
                    case "openai" -> openAiChatModel;
                    default ->
                            throw new IllegalArgumentException(
                                    "Unsupported chat-client.provider: " + props.provider()
                                            + " (expected 'ollama' or 'openai')");
                };
        return ChatClient.builder(selected).build();
    }
}
