export default function ConversationList({ conversations, currentConversationId, onSelect }) {
  return (
    <div>
      {conversations.map((c) => (
        <div
          key={c.id}
          className={"conv-item" + (c.id === currentConversationId ? " active" : "")}
          onClick={() => onSelect(c.id)}
        >
          {c.title || "(untitled)"}
        </div>
      ))}
    </div>
  );
}
