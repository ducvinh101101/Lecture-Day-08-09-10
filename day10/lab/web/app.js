const form = document.querySelector("#askForm");
const input = document.querySelector("#question");
const sendButton = document.querySelector("#sendButton");
const conversation = document.querySelector("#conversation");
const statusEl = document.querySelector("#systemStatus");
const providerBadge = document.querySelector("#providerBadge");
const confidence = document.querySelector("#confidence");
const confidenceBar = document.querySelector("#confidenceBar");
const latency = document.querySelector("#latency");
const guardStatus = document.querySelector("#guardStatus");
const routeReason = document.querySelector("#routeReason");
const agentItems = [...document.querySelectorAll("#agentFlow li")];
const sourceCards = [...document.querySelectorAll(".source-card")];

const escapeHtml = (value = "") => value.replace(/[&<>"']/g, char => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;"
}[char]));

function addMessage(role, text, citations = []) {
  const article = document.createElement("article");
  article.className = `message ${role}`;
  const pills = citations.map(citation =>
    `<span class="citation-pill">[${citation.index}] ${escapeHtml(citation.doc_id)} · ${Number(citation.score).toFixed(2)}</span>`
  ).join("");
  article.innerHTML = `
    <div class="avatar">${role === "user" ? "U" : "A"}</div>
    <div class="message-body">
      <p class="message-label">${role === "user" ? "Bạn" : "Atlas"}</p>
      <p>${escapeHtml(text)}</p>
      ${pills ? `<div class="citation-list">${pills}</div>` : ""}
    </div>`;
  conversation.append(article);
  conversation.scrollTop = conversation.scrollHeight;
  return article;
}

function addTyping() {
  const article = document.createElement("article");
  article.className = "message assistant";
  article.innerHTML = `<div class="avatar">A</div><div class="message-body"><div class="typing" aria-label="Đang xử lý"><span></span><span></span><span></span></div></div>`;
  conversation.append(article);
  conversation.scrollTop = conversation.scrollHeight;
  return article;
}

function resetTrace() {
  agentItems.forEach((item, index) => {
    item.classList.remove("done");
    item.classList.toggle("active", index === 0);
    item.querySelector("small").textContent = index === 0 ? "Đang định tuyến..." : "Đang chờ";
  });
  providerBadge.textContent = "Processing";
  providerBadge.className = "provider-badge";
}

function updateTrace(result) {
  agentItems.forEach(item => {
    const agent = item.dataset.agent;
    const event = result.events.find(entry => entry.agent === agent);
    item.classList.toggle("done", Boolean(event));
    item.classList.remove("active");
    if (event) {
      const detail = event.skipped ? "Skipped · meta intent"
        : agent === "retrieval_agent" ? `${event.retrieved} evidence`
        : agent === "quality_guard_agent" ? `${event.accepted} accepted · ${event.rejected} rejected`
        : agent === "synthesis_agent" ? `${event.provider || "offline"}`
        : "Route selected";
      item.querySelector("small").textContent = detail;
    }
  });
  const provider = result.synthesis_provider || "offline_extractive";
  providerBadge.textContent = provider === "gemini" ? "Gemini" : "Offline";
  providerBadge.className = `provider-badge ${provider === "gemini" ? "gemini" : ""}`;
  confidence.textContent = `${Math.round(result.confidence * 100)}%`;
  confidenceBar.style.width = `${Math.round(result.confidence * 100)}%`;
  latency.textContent = `${Math.round(result.latency_ms)} ms`;
  guardStatus.textContent = result.guard_passed ? "Passed" : "Review";
  routeReason.textContent = result.route_reason;
  sourceCards.forEach(card => card.classList.toggle("active", result.domain_filters.includes(card.dataset.source)));
}

async function ask(question) {
  addMessage("user", question);
  resetTrace();
  sendButton.disabled = true;
  input.disabled = true;
  const typing = addTyping();
  try {
    const response = await fetch("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, top_k: 5 })
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "Không thể xử lý câu hỏi.");
    typing.remove();
    addMessage("assistant", result.answer, result.citations);
    updateTrace(result);
  } catch (error) {
    typing.remove();
    addMessage("assistant", `Có lỗi khi xử lý: ${error.message}`);
    providerBadge.textContent = "Error";
  } finally {
    sendButton.disabled = false;
    input.disabled = false;
    input.focus();
  }
}

form.addEventListener("submit", event => {
  event.preventDefault();
  const question = input.value.trim();
  if (!question) return;
  input.value = "";
  input.style.height = "";
  ask(question);
});

input.addEventListener("keydown", event => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    form.requestSubmit();
  }
});
input.addEventListener("input", () => {
  input.style.height = "auto";
  input.style.height = `${Math.min(input.scrollHeight, 140)}px`;
});
document.querySelectorAll("[data-question]").forEach(button => {
  button.addEventListener("click", () => ask(button.dataset.question));
});

fetch("/api/health")
  .then(response => response.json())
  .then(data => {
    statusEl.classList.add("online");
    statusEl.querySelector("span:last-child").textContent =
      `${data.collection} · ${data.gemini_configured ? "Gemini ready" : "Offline mode"}`;
  })
  .catch(() => statusEl.querySelector("span:last-child").textContent = "Mất kết nối");
