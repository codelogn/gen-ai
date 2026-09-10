import { useRef, useState } from "react";

export default function Composer({ onSend, disabled }) {
  const [value, setValue] = useState("");
  const textareaRef = useRef(null);

  async function send() {
    const content = value.trim();
    if (!content) return;
    setValue("");
    await onSend(content);
    textareaRef.current?.focus();
  }

  function handleKeyDown(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  }

  return (
    <div className="composer">
      <textarea
        ref={textareaRef}
        rows={2}
        placeholder="Type a message..."
        value={value}
        disabled={disabled}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
      />
      <button onClick={send} disabled={disabled}>
        Send
      </button>
    </div>
  );
}
