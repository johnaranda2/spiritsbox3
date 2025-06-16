let chatHistory = [];

function sendMessage() {
  const input = document.getElementById("userInput");
  const message = input.value.trim();
  if (!message) return;

  chatHistory.push({ role: "user", content: message });
  updateChat();

  fetch("/recommendations_llm", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ messages: chatHistory })
  })
  .then(res => res.json())
  .then(data => {
    if (data.reply) {
      chatHistory.push({ role: "assistant", content: data.reply });
    } else if (data.error) {
      chatHistory.push({ role: "assistant", content: "⚠️ Error del servidor: " + data.error });
    } else {
      chatHistory.push({ role: "assistant", content: "⚠️ Respuesta inesperada del servidor." });
    }
    updateChat();
  })
  .catch(err => {
    chatHistory.push({ role: "assistant", content: "⚠️ Error de conexión: " + err.message });
    updateChat();
  });

  input.value = "";
}

function updateChat() {
  const chatBox = document.getElementById("chat-box");
  chatBox.innerHTML = chatHistory.map(m => {
    const cls = m.role === "user" ? "chat-bubble user" : "chat-bubble assistant";
    return `<div class="${cls}">${m.content}</div>`;
  }).join("");
  chatBox.scrollTop = chatBox.scrollHeight;
}
