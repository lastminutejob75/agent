import { api } from "../../lib/api";

/** Liste téléchargeable des documents joints à une réponse questionnaire V2. */
export default function QuestionnaireV2DocumentsList({ documents }) {
  const items = Array.isArray(documents) ? documents : [];
  if (!items.length) return null;

  return (
    <div className="mt-4">
      <div className="text-xs font-black uppercase tracking-wide text-[#64748B]">Documents joints</div>
      <ul className="mt-2 space-y-2">
        {items.map((doc) => {
          const href = doc?.id ? api.tenantDownloadQuestionnaireV2Document(doc.id) : "";
          return (
            <li key={doc.id || doc.filename}>
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
            </li>
          );
        })}
      </ul>
    </div>
  );
}
