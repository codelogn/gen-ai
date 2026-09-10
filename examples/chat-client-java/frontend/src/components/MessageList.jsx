import { useEffect, useRef } from "react";

export default function MessageList({ messages, conversationSelected }) {
  const containerRef = useRef(null);

  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [messages]);

  return (
    <div className="messages" ref={containerRef}>
      {messages.length === 0 ? (
        <div className="empty-state">
          {conversationSelected ? "No messages yet — say something." : "Select or create a conversation to start."}
        </div>
      ) : (
        messages.map((m) => (
          <div key={m.id} className={`msg ${m.role}`}>
            {m.content}
          </div>
        ))
      )}
    </div>
  );
}
