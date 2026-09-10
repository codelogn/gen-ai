import { useCallback, useEffect, useState } from "react";
import { api, uploadFile } from "./api.js";
import Sidebar from "./components/Sidebar.jsx";
import MessageList from "./components/MessageList.jsx";
import Composer from "./components/Composer.jsx";
import UploadRow from "./components/UploadRow.jsx";

export default function App() {
  const [conversations, setConversations] = useState([]);
  const [currentConversationId, setCurrentConversationId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [uploads, setUploads] = useState([]);
  const [sending, setSending] = useState(false);

  const loadConversations = useCallback(async () => {
    setConversations(await api("/conversations"));
  }, []);

  const loadMessages = useCallback(async (conversationId) => {
    setMessages(await api(`/conversations/${conversationId}/messages`));
  }, []);

  const loadUploads = useCallback(async (conversationId) => {
    setUploads(await api(`/conversations/${conversationId}/uploads`));
  }, []);

  useEffect(() => {
    loadConversations();
  }, [loadConversations]);

  async function handleCreateConversation() {
    const { id } = await api("/conversations", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });
    await loadConversations();
    await handleSelectConversation(id);
  }

  async function handleSelectConversation(id) {
    setCurrentConversationId(id);
    await Promise.all([loadMessages(id), loadUploads(id)]);
  }

  async function handleSend(content) {
    if (!content || !currentConversationId) return;
    setSending(true);
    try {
      await api(`/conversations/${currentConversationId}/messages`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content }),
      });
    } catch (e) {
      alert("Failed to send message: " + e.message);
    }
    await loadMessages(currentConversationId);
    setSending(false);
  }

  async function handleUpload(file) {
    if (!file || !currentConversationId) return;
    try {
      await uploadFile(currentConversationId, file);
      await loadUploads(currentConversationId);
    } catch (e) {
      alert("Upload failed: " + e.message);
    }
  }

  return (
    <div className="layout">
      <Sidebar
        conversations={conversations}
        currentConversationId={currentConversationId}
        onCreate={handleCreateConversation}
        onSelect={handleSelectConversation}
      />
      <div className="main">
        <MessageList messages={messages} conversationSelected={currentConversationId !== null} />
        {currentConversationId && <UploadRow uploads={uploads} onUpload={handleUpload} />}
        {currentConversationId && <Composer onSend={handleSend} disabled={sending} />}
      </div>
    </div>
  );
}
