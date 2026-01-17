(() => {
  const MAX_LEN = 500;

  const chat = document.getElementById("chat");
  const composer = document.getElementById("composer");
  const input = document.getElementById("messageInput");
  const sendBtn = document.getElementById("sendBtn");
  const charCounter = document.getElementById("charCounter");
  const hint = document.getElementById("hint");
  const typing = document.getElementById("typing");
  const errorBox = document.getElementById("errorBox");
  const statusPill = document.getElementById("statusPill");
  const terminalHint = document.getElementById("terminalHint");

  const humanBtn = document.getElementById("humanBtn");
  const humanModal = document.getElementById("humanModal");
  const closeHumanModalBtn = document.getElementById("closeHumanModalBtn");
  const copyPhoneBtn = document.getElementById("copyPhoneBtn");
  const phoneValue = document.getElementById("phoneValue");

  let conversationId = null;
  let es = null;
  let reconnectTimer = null;
  let lastEventAt = Date.now();
  let pendingPartialId = null;

  function setStatus(text, kind = "ok") {
    statusPill.textContent = text;
    statusPill.dataset.kind = kind;
  }

  function showTyping(show) {
    typing.style.display = show ? "flex" : "none";
    typing.setAttribute("aria-hidden", show ? "false" : "true");
  }

  function showError(msg) {
    if (!msg) {
      errorBox.hidden = true;
      errorBox.textContent = "";
      return;
    }
    errorBox.hidden = false;
    errorBox.textContent = msg;
  }

  function escapeHtml(s) {
    return (s || "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function addMessage(role, text) {
    const wrapper = document.createElement("div");
    wrapper.className = `msg ${role}`;

    const bubble = document.createElement("div");
    bubble.className = "bubble";
    bubble.innerHTML = escapeHtml(text).replaceAll("\n", "<br>");

    wrapper.appendChild(bubble);
    chat.appendChild(wrapper);
    chat.scrollTop = chat.scrollHeight;
  }

  function upsertPartial(text) {
    if (pendingPartialId) {
      const el = document.getElementById(pendingPartialId);
      if (el) {
        el.querySelector(".bubble").innerHTML = escapeHtml(text).replaceAll("\n", "<br>");
        chat.scrollTop = chat.scrollHeight;
        return;
      }
    }

    const id = `partial-${Date.now()}`;
    pendingPartialId = id;

    const wrapper = document.createElement("div");
    wrapper.className = "msg agent partial";
    wrapper.id = id;

    const bubble = document.createElement("div");
    bubble.className = "bubble";
    bubble.innerHTML = escapeHtml(text).replaceAll("\n", "<br>");

    wrapper.appendChild(bubble);
    chat.appendChild(wrapper);
    chat.scrollTop = chat.scrollHeight;
  }

  function clearPartial() {
    if (!pendingPartialId) return;
    const el = document.getElementById(pendingPartialId);
    if (el) el.remove();
    pendingPartialId = null;
  }

  function validateMessage(text) {
    const t = (text || "").trim();
    if (!t) {
      showError("Le message ne peut pas être vide");
      return false;
    }
    if (t.length > MAX_LEN) {
      showError(`Message trop long (${t.length}/${MAX_LEN} caractères)`);
      return false;
    }
    showError("");
    return true;
  }

  function updateCounter() {
    const len = input.value.length;
    charCounter.textContent = `${len}/${MAX_LEN}`;
    charCounter.dataset.level = len > MAX_LEN ? "error" : len > 450 ? "warn" : "ok";
    hint.textContent = "";
  }

  input.addEventListener("input", updateCounter);
  updateCounter();

  function connectSSE() {
    if (!conversationId) return;

    if (es) {
      es.close();
      es = null;
    }

    setStatus("Connexion…", "warn");
    showTyping(false);

    es = new EventSource(`/stream/${conversationId}`);

    es.onopen = () => {
      setStatus("Connecté", "ok");
    };

    es.onmessage = (e) => {
      lastEventAt = Date.now();
      if (!e.data) return;

      let payload = null;
      try {
        payload = JSON.parse(e.data);
      } catch (err) {
        showError("Erreur de parsing SSE");
        return;
      }

      handleEvent(payload);
    };

    es.onerror = () => {
      setStatus("Déconnecté", "error");
      scheduleReconnect();
    };
  }

  function scheduleReconnect() {
    if (reconnectTimer) return;
    reconnectTimer = setTimeout(() => {
      reconnectTimer = null;
      connectSSE();
    }, 1200);
  }

  function handleEvent(payload) {
    const type = payload.type;

    if (type === "partial") {
      showTyping(true);
      const text = payload.text || "…";
      upsertPartial(text);
      return;
    }

    if (type === "final") {
      showTyping(false);
      clearPartial();
      addMessage("agent", payload.text || "");
      
      // Si état terminal => verrouiller l'UI
      if (payload.conv_state === "CONFIRMED" || payload.conv_state === "TRANSFERRED") {
        lockConversation(payload.conv_state);
      }
      return;
    }

    if (type === "transfer") {
      showTyping(false);
      clearPartial();

      if (payload.silent) {
        // Si transfert silencieux mais état terminal, on verrouille quand même
        if (payload.conv_state === "TRANSFERRED") {
          lockConversation("TRANSFERRED");
        }
        return;
      }

      if (payload.text) addMessage("agent", payload.text);
      else addMessage("agent", "Transfert…");
      
      // Si état terminal => verrouiller l'UI
      if (payload.conv_state === "TRANSFERRED") {
        lockConversation("TRANSFERRED");
      }
      return;
    }

    if (type === "error") {
      showTyping(false);
      clearPartial();
      showError(payload.message || "Erreur serveur, veuillez réessayer");
      return;
    }
  }

  async function sendMessage(text) {
    showError("");
    showTyping(true);

    addMessage("user", text);

    const body = {
      message: text,
      conversation_id: conversationId,
    };

    const res = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    if (!res.ok) {
      showTyping(false);
      showError("Erreur envoi. Réessayez.");
      return;
    }

    const data = await res.json();
    if (!conversationId) {
      conversationId = data.conversation_id;
      connectSSE();
    }
  }

  composer.addEventListener("submit", async (e) => {
    e.preventDefault();
    const text = input.value;
    if (!validateMessage(text)) return;

    input.value = "";
    updateCounter();
    await sendMessage(text.trim());
  });

  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendBtn.click();
    }
  });

  humanBtn.addEventListener("click", () => {
    phoneValue.textContent = "+33 6 00 00 00 00";
    humanModal.showModal();
  });

  closeHumanModalBtn.addEventListener("click", () => humanModal.close());

  copyPhoneBtn.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(phoneValue.textContent);
      copyPhoneBtn.textContent = "Copié";
      setTimeout(() => (copyPhoneBtn.textContent = "Copier"), 1000);
    } catch {
      copyPhoneBtn.textContent = "Impossible";
      setTimeout(() => (copyPhoneBtn.textContent = "Copier"), 1000);
    }
  });

  function lockConversation(state) {
    const textarea = document.querySelector("#messageInput");
    const sendBtn = document.querySelector("#sendBtn");
    const hintEl = document.querySelector("#terminalHint");

    textarea.disabled = true;
    sendBtn.disabled = true;

    if (hintEl) {
      hintEl.classList.remove("hidden");
      hintEl.textContent =
        state === "CONFIRMED"
          ? "✅ Rendez-vous confirmé. Conversation terminée."
          : "🔁 Transfert humain en cours. Conversation terminée.";
    }
  }

  setStatus("Connecté", "ok");
  showTyping(false);
})();
