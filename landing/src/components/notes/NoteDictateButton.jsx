import { useNoteDictation, appendDictatedText, formatDictationElapsed } from "../../lib/useNoteDictation.js";

/**
 * Bouton « Dicter » (tailwind) branché sur un champ note.
 * Concatène le texte transcrit à `value` via `onChange`.
 */
export default function NoteDictateButton({ value, onChange, onError, disabled = false, className = "" }) {
  const { recording, transcribing, supported, toggle, elapsedMs } = useNoteDictation({
    onText: (text) => onChange?.(appendDictatedText(value, text)),
    onError,
  });

  if (!supported) return null;

  const label = transcribing
    ? "Transcription…"
    : recording
      ? `Arrêter · ${formatDictationElapsed(elapsedMs)}`
      : "Dicter";

  return (
    <button
      type="button"
      onClick={toggle}
      disabled={disabled || transcribing}
      aria-pressed={recording}
      className={
        className ||
        `inline-flex shrink-0 items-center gap-2 rounded-xl border px-3 py-2 text-sm font-black transition disabled:opacity-60 ${
          recording
            ? "border-[#E11D48] bg-[#FFF1F3] text-[#E11D48]"
            : "border-[#6941C6] bg-white text-[#5B34B0] hover:bg-[#F4F3FF]"
        }`
      }
    >
      <span
        className={`grid h-4 w-4 place-items-center rounded-full text-[10px] ${
          recording ? "animate-pulse bg-[#E11D48] text-white" : "bg-[#F4F3FF] text-[#5B34B0]"
        }`}
      >
        ●
      </span>
      {label}
    </button>
  );
}
