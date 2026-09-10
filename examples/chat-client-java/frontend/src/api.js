// Vite's build-time env var — the analog of the Python sibling's runtime
// `window.CHAT_CLIENT_API_BASE` override. Baked in at build time since
// this frontend ships as its own built container image.
const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:9001";

export async function api(path, options = {}) {
  const resp = await fetch(`${API_BASE}${path}`, options);
  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(`${resp.status}: ${text}`);
  }
  const length = resp.headers.get("content-length");
  return length === "0" ? null : resp.json();
}

export async function uploadFile(conversationId, file) {
  const formData = new FormData();
  formData.append("file", file);
  const resp = await fetch(`${API_BASE}/conversations/${conversationId}/upload`, {
    method: "POST",
    body: formData,
  });
  if (!resp.ok) {
    throw new Error(await resp.text());
  }
  return resp.json();
}
