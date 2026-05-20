import { useCallback, useEffect, useRef, useState } from "react";

const MAX_LEN = 500;

/**
 * Logique du widget /frontend (POST chat + SSE stream), pour la fiche publique praticien.
 * @param {{ apiBase: string, slug: string, welcomeMessage?: string }} opts
 */
export function usePublicPraticienChat({ apiBase, slug, welcomeMessage }) {
  const [messages, setMessages] = useState(() => {
    const intro = (welcomeMessage || "").trim();
    if (!intro) return [];
    return [{ role: "agent", text: intro, id: "welcome" }];
  });
  const [input, setInput] = useState("");
  const [typing, setTyping] = useState(false);
  const [error, setError] = useState("");
  const [locked, setLocked] = useState(false);
  const [status, setStatus] = useState("idle");

  const conversationIdRef = useRef(null);
  const esRef = useRef(null);
  const partialIdRef = useRef(null);
  const reconnectTimerRef = useRef(null);

  const chatUrl = `${apiBase}/api/public/praticiens/${encodeURIComponent(slug)}/chat`;
  const streamUrl = (convId) =>
    `${apiBase}/api/public/praticiens/${encodeURIComponent(slug)}/stream/${encodeURIComponent(convId)}`;

  const closeSSE = useCallback(() => {
    if (esRef.current) {
      esRef.current.close();
      esRef.current = null;
    }
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
  }, []);

  useEffect(() => () => closeSSE(), [closeSSE]);

  const appendMessage = useCallback((role, text, extra = {}) => {
    const id = `${role}-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
    setMessages((prev) => [...prev, { role, text, id, ...extra }]);
    return id;
  }, []);

  const upsertPartial = useCallback((text) => {
    setMessages((prev) => {
      const pid = partialIdRef.current;
      if (pid) {
        const idx = prev.findIndex((m) => m.id === pid);
        if (idx >= 0) {
          const next = [...prev];
          next[idx] = { ...next[idx], text };
          return next;
        }
      }
      const id = `partial-${Date.now()}`;
      partialIdRef.current = id;
      return [...prev, { role: "agent", text, id, partial: true }];
    });
  }, []);

  const clearPartial = useCallback(() => {
    const pid = partialIdRef.current;
    if (!pid) return;
    setMessages((prev) => prev.filter((m) => m.id !== pid));
    partialIdRef.current = null;
  }, []);

  const lockConversation = useCallback((state) => {
    setLocked(true);
    setTyping(false);
    if (state === "CONFIRMED") {
      appendMessage(
        "agent",
        "Votre rendez-vous est confirmé. La conversation est terminée — le cabinet vous recontactera si besoin."
      );
    } else if (state === "TRANSFERRED") {
      appendMessage(
        "agent",
        "Votre demande a été transmise au cabinet. Un membre de l'équipe vous recontactera."
      );
    }
  }, [appendMessage]);

  const handleEvent = useCallback(
    (payload) => {
      const type = payload.type;

      if (type === "partial") {
        setTyping(true);
        upsertPartial(payload.text || "…");
        return;
      }

      if (type === "final") {
        setTyping(false);
        clearPartial();
        const slots = Array.isArray(payload.slots) ? payload.slots : [];
        if (payload.text) {
          appendMessage("agent", payload.text, slots.length ? { slots } : {});
        }
        if (payload.conv_state === "CONFIRMED" || payload.conv_state === "TRANSFERRED") {
          lockConversation(payload.conv_state);
        }
        return;
      }

      if (type === "transfer") {
        setTyping(false);
        clearPartial();
        const slots = Array.isArray(payload.slots) ? payload.slots : [];
        if (!payload.silent && payload.text) {
          appendMessage("agent", payload.text, slots.length ? { slots } : {});
        }
        if (payload.conv_state === "TRANSFERRED") lockConversation("TRANSFERRED");
        return;
      }

      if (type === "error") {
        setTyping(false);
        clearPartial();
        setError(payload.message || "Erreur serveur, veuillez réessayer.");
      }
    },
    [appendMessage, clearPartial, lockConversation, upsertPartial]
  );

  const connectSSE = useCallback(() => {
    const convId = conversationIdRef.current;
    if (!convId) return;

    closeSSE();
    setStatus("connecting");

    const es = new EventSource(streamUrl(convId));
    esRef.current = es;

    es.onopen = () => setStatus("connected");
    es.onmessage = (e) => {
      if (!e.data) return;
      try {
        handleEvent(JSON.parse(e.data));
      } catch {
        setError("Erreur de réception des messages.");
      }
    };
    es.onerror = () => {
      setStatus("disconnected");
      if (reconnectTimerRef.current) return;
      reconnectTimerRef.current = setTimeout(() => {
        reconnectTimerRef.current = null;
        connectSSE();
      }, 1200);
    };
  }, [closeSSE, handleEvent, streamUrl]);

  const sendMessage = useCallback(
    async (text) => {
      const trimmed = (text || "").trim();
      if (!trimmed || locked) return false;
      if (trimmed.length > MAX_LEN) {
        setError(`Message trop long (${trimmed.length}/${MAX_LEN} caractères).`);
        return false;
      }

      setError("");
      setTyping(true);
      appendMessage("user", trimmed);

      try {
        const res = await fetch(chatUrl, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            message: trimmed,
            conversation_id: conversationIdRef.current,
          }),
        });
        if (!res.ok) {
          setTyping(false);
          setError("Impossible d'envoyer le message. Réessayez.");
          return false;
        }
        const data = await res.json();
        if (!conversationIdRef.current) {
          conversationIdRef.current = data.conversation_id;
          connectSSE();
        }
        return true;
      } catch {
        setTyping(false);
        setError("Connexion impossible. Vérifiez votre réseau.");
        return false;
      }
    },
    [appendMessage, chatUrl, connectSSE, locked]
  );

  const submit = useCallback(
    async (e) => {
      e?.preventDefault?.();
      const ok = await sendMessage(input);
      if (ok) setInput("");
    },
    [input, sendMessage]
  );

  return {
    messages,
    input,
    setInput,
    typing,
    error,
    locked,
    status,
    maxLen: MAX_LEN,
    submit,
    sendMessage,
  };
}
