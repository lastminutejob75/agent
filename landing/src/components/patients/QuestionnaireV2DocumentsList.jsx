import { useState } from "react";
import { api } from "../../lib/api";

/** Liste téléchargeable des documents joints à une réponse questionnaire V2. */
export default function QuestionnaireV2DocumentsList({
  documents,
  allowDelete = false,
  onDocumentDeleted,
  notify,
}) {
  const items = Array.isArray(documents) ? documents : [];
  const [deletingId, setDeletingId] = useState("");
  if (!items.length) return null;

  const notifyFn = (msg, opts) => {
    if (typeof notify === "function") notify(msg, opts);
  };

  const handleDelete = async (doc) => {
    if (!doc?.id || deletingId) return;
    if (!window.confirm(`Supprimer « ${doc.filename || "ce document"} » ?`)) return;
    setDeletingId(String(doc.id));
    try {
      await api.tenantDeleteQuestionnaireV2Document(doc.id);
      notifyFn("Document supprimé");
      if (typeof onDocumentDeleted === "function") onDocumentDeleted(doc.id);
    } catch (e) {
      notifyFn(e?.message || "Suppression impossible", { sticky: true });
    } finally {
      setDeletingId("");
    }
  };

  return (
    <div className="mt-4">
      <div className="text-xs font-black uppercase tracking-wide text-[#64748B]">Documents joints</div>
      <ul className="mt-2 space-y-2">
        {items.map((doc) => {
          const href = doc?.id ? api.tenantDownloadQuestionnaireV2Document(doc.id) : "";
          const isDeleting = deletingId === String(doc.id);
          return (
            <li
              key={doc.id || doc.filename}
              className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-[#EEF3F8] px-3 py-2"
            >
              {href ? (
                <a
                  href={href}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 text-sm font-semibold text-[#007F88] hover:underline"
                >
                  <span aria-hidden>📎</span>
                  {doc.filename || "Document"}
                </a>
              ) : (
                <span className="text-sm text-[#475569]">{doc.filename}</span>
              )}
              {allowDelete && doc?.id ? (
                <button
                  type="button"
                  disabled={isDeleting}
                  onClick={() => void handleDelete(doc)}
                  className="rounded-lg border border-[#FECACA] bg-[#FEF2F2] px-2.5 py-1 text-xs font-black text-[#B91C1C] hover:bg-[#FEE2E2] disabled:opacity-60"
                >
                  {isDeleting ? "…" : "Supprimer"}
                </button>
              ) : null}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
