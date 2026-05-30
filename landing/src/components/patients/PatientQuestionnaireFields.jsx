/**
 * Schéma par défaut (miroir du backend `patient_questionnaire.QUESTIONNAIRE_FIELDS`).
 * Sert de repli si le backend n'a pas encore répondu (ex. déploiement en cours),
 * pour que le formulaire affiche toujours ses champs.
 */
export const DEFAULT_PATIENT_QUESTIONNAIRE_SCHEMA = [
  { id: "birth_date", label: "Date de naissance", type: "date" },
  { id: "treating_physician_name", label: "Médecin traitant", type: "text" },
  { id: "treating_physician_city", label: "Ville du médecin traitant", type: "text" },
  { id: "allergies", label: "Allergies connues", type: "textarea" },
  { id: "current_treatments", label: "Traitements en cours", type: "textarea" },
  { id: "medical_history", label: "Antécédents médicaux", type: "textarea" },
  { id: "emergency_contact", label: "Personne à contacter en cas d'urgence", type: "text" },
  { id: "main_reason", label: "Motif principal de consultation", type: "textarea" },
];

/** Normalise schéma MVP (`id`) ou V2 (`field_id`). */
export function normalizeQuestionnaireSchema(raw) {
  if (!Array.isArray(raw)) return [];
  return raw
    .map((field) => ({
      id: field.id || field.field_id,
      label: field.label || field.field_id || field.id || "Champ",
      type: field.type || "text",
      options: Array.isArray(field.options) ? field.options : [],
      required: Boolean(field.required),
    }))
    .filter((f) => f.id);
}

function optionLabel(value, optionLabels) {
  if (optionLabels && optionLabels[value]) return optionLabels[value];
  return String(value || "").replace(/_/g, " ");
}

/**
 * Rendu des champs d'un questionnaire patient à partir d'un schéma
 * [{ id, label, type }]. Partagé entre la fiche praticien et la page patient.
 */
export default function PatientQuestionnaireFields({
  schema,
  values,
  onChange,
  disabled = false,
  optionLabels = null,
}) {
  const fields =
    normalizeQuestionnaireSchema(schema).length > 0
      ? normalizeQuestionnaireSchema(schema)
      : DEFAULT_PATIENT_QUESTIONNAIRE_SCHEMA;

  return (
    <div className="flex flex-col gap-3.5">
      {fields.map((field) => {
        const value = values?.[field.id];
        const commonClass =
          "w-full rounded-xl border border-[#DDE7F1] px-3 py-2.5 text-sm font-semibold text-[#0A1628] outline-none focus:border-[#009CA4] disabled:bg-slate-50 disabled:text-slate-400";

        if (field.type === "boolean") {
          return (
            <label key={field.id} className="flex items-center gap-2.5 text-sm font-bold text-[#334155]">
              <input
                id={`q-${field.id}`}
                type="checkbox"
                checked={Boolean(value)}
                disabled={disabled}
                onChange={(e) => onChange(field.id, e.target.checked)}
                className="h-4 w-4 rounded border-[#CBD5E1]"
              />
              {field.label}
            </label>
          );
        }

        if (field.type === "select") {
          return (
            <label key={field.id} htmlFor={`q-${field.id}`} className="flex flex-col gap-1.5 text-sm font-bold text-[#334155]">
              {field.label}
              <select
                id={`q-${field.id}`}
                value={value ?? ""}
                disabled={disabled}
                onChange={(e) => onChange(field.id, e.target.value)}
                className={commonClass}
              >
                <option value="">— Choisir —</option>
                {field.options.map((opt) => (
                  <option key={opt} value={opt}>
                    {optionLabel(opt, optionLabels)}
                  </option>
                ))}
              </select>
            </label>
          );
        }

        const common = {
          id: `q-${field.id}`,
          value: value ?? "",
          disabled,
          onChange: (e) => onChange(field.id, e.target.value),
          className: commonClass,
        };

        return (
          <label key={field.id} htmlFor={common.id} className="flex flex-col gap-1.5 text-sm font-bold text-[#334155]">
            {field.label}
            {field.type === "textarea" ? (
              <textarea {...common} rows={3} className={`${common.className} resize-none`} />
            ) : (
              <input {...common} type={field.type === "date" ? "date" : field.type === "email" ? "email" : field.type === "phone" ? "tel" : "text"} />
            )}
          </label>
        );
      })}
    </div>
  );
}
