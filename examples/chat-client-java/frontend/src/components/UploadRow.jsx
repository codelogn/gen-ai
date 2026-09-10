import { useRef } from "react";

export default function UploadRow({ uploads, onUpload }) {
  const fileInputRef = useRef(null);

  async function handleUploadClick() {
    const file = fileInputRef.current?.files?.[0];
    if (!file) return;
    await onUpload(file);
    fileInputRef.current.value = "";
  }

  const summary = uploads.length ? uploads.map((u) => `${u.filename} (${u.chunk_count} chunks)`).join(", ") : "";

  return (
    <div className="upload-row">
      <input ref={fileInputRef} type="file" id="file-input" accept=".txt,.md" />
      <button onClick={handleUploadClick}>Upload document</button>
      <span className="uploads-list">{summary}</span>
    </div>
  );
}
