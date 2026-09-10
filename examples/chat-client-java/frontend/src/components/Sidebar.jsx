import ConversationList from "./ConversationList.jsx";

export default function Sidebar({ conversations, currentConversationId, onCreate, onSelect }) {
  return (
    <div className="sidebar">
      <button className="new-conv-btn" onClick={onCreate}>
        + New conversation
      </button>
      <h2>Conversations</h2>
      <ConversationList
        conversations={conversations}
        currentConversationId={currentConversationId}
        onSelect={onSelect}
      />
    </div>
  );
}
