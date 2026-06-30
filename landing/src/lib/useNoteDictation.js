import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api.js";

/**
 * Dictée vocale réutilisable pour les champs « note ».
 * Enregistre le micro (MediaRecorder), transcrit via /api/tenant/notes/transcribe
 * puis renvoie le texte transcrit à `onText` (à concaténer dans le champ note).
 *
 * Expose aussi un retour visuel : minuteur (`elapsedMs`), niveau micro (`level`
 * 0..1) et l'URL du dernier enregistrement (`lastAudioUrl`) pour réécoute.
 */
export function useNoteDictation({ onText, onError } = {}) {
  const [recording, setRecording] = useState(false);
  const [transcribing, setTranscribing] = useState(false);
  const [elapsedMs, setElapsedMs] = useState(0);
  const [level, setLevel] = useState(0);
  const [lastAudioUrl, setLastAudioUrl] = useState("");

  const streamRef = useRef(null);
  const recorderRef = useRef(null);
  const chunksRef = useRef([]);
  const audioCtxRef = useRef(null);
  const analyserRef = useRef(null);
  const rafRef = useRef(0);
  const startTsRef = useRef(0);
  const lastUrlRef = useRef("");

  const supported =
    typeof navigator !== "undefined" &&
    !!navigator.mediaDevices &&
    typeof navigator.mediaDevices.getUserMedia === "function" &&
    typeof MediaRecorder !== "undefined";

  const stopMeter = useCallback(() => {
    if (rafRef.current) {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = 0;
    }
    const ctx = audioCtxRef.current;
    if (ctx) {
      try {
        ctx.close();
      } catch {
        /* ignore */
      }
      audioCtxRef.current = null;
    }
    analyserRef.current = null;
    setLevel(0);
  }, []);

  const startMeter = useCallback((stream) => {
    try {
      const Ctx = window.AudioContext || window.webkitAudioContext;
      if (!Ctx) return;
      const ctx = new Ctx();
      const source = ctx.createMediaStreamSource(stream);
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 512;
      source.connect(analyser);
      audioCtxRef.current = ctx;
      analyserRef.current = analyser;
      const data = new Uint8Array(analyser.frequencyBinCount);
      const tick = () => {
        const a = analyserRef.current;
        if (!a) return;
        a.getByteTimeDomainData(data);
        let sum = 0;
        for (let i = 0; i < data.length; i += 1) {
          const v = (data[i] - 128) / 128;
          sum += v * v;
        }
        const rms = Math.sqrt(sum / data.length);
        setLevel(Math.min(1, rms * 3));
        if (startTsRef.current) setElapsedMs(Date.now() - startTsRef.current);
        rafRef.current = requestAnimationFrame(tick);
      };
      rafRef.current = requestAnimationFrame(tick);
    } catch {
      /* metering optionnel */
    }
  }, []);

  const releaseStream = useCallback(() => {
    const stream = streamRef.current;
    if (stream) {
      stream.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
    stopMeter();
  }, [stopMeter]);

  useEffect(
    () => () => {
      try {
        const rec = recorderRef.current;
        if (rec && rec.state === "recording") rec.stop();
      } catch {
        /* ignore */
      }
      releaseStream();
      if (lastUrlRef.current) {
        URL.revokeObjectURL(lastUrlRef.current);
        lastUrlRef.current = "";
      }
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
        if (blob.size > 0) {
          if (lastUrlRef.current) URL.revokeObjectURL(lastUrlRef.current);
          const url = URL.createObjectURL(blob);
          lastUrlRef.current = url;
          setLastAudioUrl(url);
        }
        void transcribe(blob);
      };
      rec.start();
      recorderRef.current = rec;
      startTsRef.current = Date.now();
      setElapsedMs(0);
      if (lastUrlRef.current) {
        URL.revokeObjectURL(lastUrlRef.current);
        lastUrlRef.current = "";
        setLastAudioUrl("");
      }
      startMeter(stream);
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
  }, [recording, transcribing, supported, stop, releaseStream, startMeter, transcribe, onError]);

  return { recording, transcribing, supported, toggle, stop, elapsedMs, level, lastAudioUrl };
}

/** Concatène proprement un fragment dicté à la valeur existante du champ. */
export function appendDictatedText(previous, addition) {
  const prev = String(previous || "");
  const add = String(addition || "").trim();
  if (!add) return prev;
  const sep = prev && !/\s$/.test(prev) ? " " : "";
  return prev + sep + add;
}

/** Formate une durée en mm:ss pour le minuteur de dictée. */
export function formatDictationElapsed(ms) {
  const total = Math.max(0, Math.floor(Number(ms || 0) / 1000));
  const m = Math.floor(total / 60);
  const s = total % 60;
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}
