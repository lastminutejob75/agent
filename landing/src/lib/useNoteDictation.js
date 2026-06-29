import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api.js";

/**
 * Dictée vocale réutilisable pour les champs « note ».
 * Enregistre le micro (MediaRecorder), transcrit via /api/tenant/notes/transcribe
 * puis renvoie le texte transcrit à `onText` (à concaténer dans le champ note).
 *
 * Usage :
 *   const { recording, transcribing, supported, toggle } = useNoteDictation({
 *     onText: (t) => setNote((prev) => appendDictated(prev, t)),
 *     onError: (msg) => notify(msg),
 *   });
 */
export function useNoteDictation({ onText, onError } = {}) {
  const [recording, setRecording] = useState(false);
  const [transcribing, setTranscribing] = useState(false);
  const streamRef = useRef(null);
  const recorderRef = useRef(null);
  const chunksRef = useRef([]);

  const supported =
    typeof navigator !== "undefined" &&
    !!navigator.mediaDevices &&
    typeof navigator.mediaDevices.getUserMedia === "function" &&
    typeof MediaRecorder !== "undefined";

  const releaseStream = useCallback(() => {
    const stream = streamRef.current;
    if (stream) {
      stream.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
  }, []);

  useEffect(
    () => () => {
      try {
        const rec = recorderRef.current;
        if (rec && rec.state === "recording") rec.stop();
      } catch {
        /* ignore */
      }
      releaseStream();
    },
    [releaseStream],
  );

  const transcribe = useCallback(
    async (blob) => {
      if (!blob || blob.size === 0) return;
      setTranscribing(true);
      try {
        const res = await api.tenantTranscribeNote(blob);
        const text = String(res?.transcription || "").trim();
        if (text) onText?.(text);
        else onError?.("Aucune parole détectée. Réessayez ou saisissez la note.");
      } catch (e) {
        onError?.(e?.message || "La dictée n'a pas pu être transcrite.");
      } finally {
        setTranscribing(false);
      }
    },
    [onText, onError],
  );

  const stop = useCallback(() => {
    const rec = recorderRef.current;
    if (rec && rec.state === "recording") {
      try {
        rec.stop();
      } catch {
        releaseStream();
        setRecording(false);
      }
    } else {
      releaseStream();
      setRecording(false);
    }
  }, [releaseStream]);

  const toggle = useCallback(async () => {
    if (recording) {
      stop();
      return;
    }
    if (transcribing) return;
    if (!supported) {
      onError?.("La dictée vocale n'est pas disponible sur ce navigateur/appareil.");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      const rec = new MediaRecorder(stream);
      chunksRef.current = [];
      rec.ondataavailable = (event) => {
        if (event.data && event.data.size) chunksRef.current.push(event.data);
      };
      rec.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: rec.mimeType || "audio/webm" });
        releaseStream();
        setRecording(false);
        void transcribe(blob);
      };
      rec.start();
      recorderRef.current = rec;
      setRecording(true);
    } catch (e) {
      releaseStream();
      setRecording(false);
      const name = e?.name || "";
      onError?.(
        name === "NotAllowedError" || name === "SecurityError"
          ? "Micro non autorisé. Autorisez l'accès au microphone dans le navigateur."
          : "Impossible d'accéder au microphone.",
      );
    }
  }, [recording, transcribing, supported, stop, releaseStream, transcribe, onError]);

  return { recording, transcribing, supported, toggle, stop };
}

/** Concatène proprement un fragment dicté à la valeur existante du champ. */
export function appendDictatedText(previous, addition) {
  const prev = String(previous || "");
  const add = String(addition || "").trim();
  if (!add) return prev;
  const sep = prev && !/\s$/.test(prev) ? " " : "";
  return prev + sep + add;
}
