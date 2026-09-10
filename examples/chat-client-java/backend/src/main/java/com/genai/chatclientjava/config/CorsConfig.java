package com.genai.chatclientjava.config;

import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.config.annotation.CorsRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

/**
 * Wide open, same as the Python sibling's CORSMiddleware(allow_origins=["*"])
 * — this is a local reference example (frontend and backend run as
 * separate containers on separate ports), not something with a real
 * production CORS policy to demonstrate.
 */
@Configuration
public class CorsConfig implements WebMvcConfigurer {
    @Override
    public void addCorsMappings(CorsRegistry registry) {
        registry.addMapping("/**")
                .allowedOriginPatterns("*")
                .allowedMethods("*")
                .allowedHeaders("*");
    }
}
