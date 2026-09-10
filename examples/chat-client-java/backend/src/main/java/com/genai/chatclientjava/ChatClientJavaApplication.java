package com.genai.chatclientjava;

import com.genai.chatclientjava.config.ChatClientProperties;
import com.genai.chatclientjava.config.GenAiProperties;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.EnableConfigurationProperties;

@SpringBootApplication
@EnableConfigurationProperties({GenAiProperties.class, ChatClientProperties.class})
public class ChatClientJavaApplication {
    public static void main(String[] args) {
        SpringApplication.run(ChatClientJavaApplication.class, args);
    }
}
