// chat.js
let chatboxVisible = false;
let chatHistory = [];

function toggleChat() {
  const chat = document.getElementById("chatbox");
  chatboxVisible = !chatboxVisible;
  chat.classList.toggle("chat-hidden", !chatboxVisible);
}

document.getElementById("chat-toggle").addEventListener("click", toggleChat);

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
      chatHistory.push({ role: "assistant", content: data.reply });
      updateChat();
    })
    .catch(err => {
      chatHistory.push({ role: "assistant", content: "Error: " + err.message });
      updateChat();
    });

  input.value = "";
}

function updateChat() {
  const chatBox = document.getElementById("chat-box");
  chatBox.innerHTML = chatHistory.map(m => {
    const cls = m.role === "user" ? "font-weight: bold;" : "color: #5b2c83;";
    return `<div style="${cls}">${m.content}</div>`;
  }).join("");
  chatBox.scrollTop = chatBox.scrollHeight;
}
