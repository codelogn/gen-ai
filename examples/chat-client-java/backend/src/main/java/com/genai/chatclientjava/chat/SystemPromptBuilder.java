package com.genai.chatclientjava.chat;

import com.genai.chatclientjava.domain.Message;
import com.genai.chatclientjava.genai.dto.MemoryHit;
import java.util.List;
import java.util.Set;
import java.util.stream.Collectors;
import org.springframework.stereotype.Component;

/**
 * A line-for-line port of examples/chat-client-python/backend/app/main.py's
 * _build_system_prompt: recency window verbatim, then semantic message hits
 * deduped against that window's content, then document hits prefixed with
 * their filename.
 */
@Component
public class SystemPromptBuilder {

    public String build(List<Message> recent, List<MemoryHit> messageHits, List<MemoryHit> documentHits) {
        StringBuilder sb = new StringBuilder(
                "You are a helpful assistant in an ongoing conversation. "
                        + "Use the context below if relevant; otherwise just answer normally.");

        if (!recent.isEmpty()) {
            sb.append("\n\n## Recent conversation");
            for (Message m : recent) {
                sb.append('\n').append(m.getRole().toWireValue()).append(": ").append(m.getContent());
            }
        }

        Set<String> recentContents = recent.stream().map(Message::getContent).collect(Collectors.toSet());
        List<MemoryHit> relevantOlder =
                messageHits.stream().filter(h -> !recentContents.contains(h.content())).toList();
        if (!relevantOlder.isEmpty()) {
            sb.append("\n\n## Relevant earlier messages (found by semantic search)");
            for (MemoryHit hit : relevantOlder) {
                sb.append("\n- ").append(hit.content()).append(String.format(" (relevance: %.2f)", hit.score()));
            }
        }

        if (!documentHits.isEmpty()) {
            sb.append("\n\n## Relevant content from uploaded documents");
            for (MemoryHit hit : documentHits) {
                String filename = "uploaded file";
                if (hit.metadata() != null && hit.metadata().get("filename") != null) {
                    filename = String.valueOf(hit.metadata().get("filename"));
                }
                sb.append("\n- [").append(filename).append("] ").append(hit.content());
            }
        }

        return sb.toString();
    }
}
