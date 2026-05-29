/**
 * Rendu des champs d'un questionnaire patient à partir d'un schéma
 * [{ id, label, type }]. Partagé entre la fiche praticien et la page patient.
 */
export default function PatientQuestionnaireFields({ schema, values, onChange, disabled = false }) {
  const fields = Array.isArray(schema) ? schema : [];
  return (
    <div className="flex flex-col gap-3.5">
      {fields.map((field) => {
        const value = values?.[field.id] ?? "";
        const common = {
          id: `q-${field.id}`,
          value,
          disabled,
          onChange: (e) => onChange(field.id, e.target.value),
          className:
            "w-full rounded-xl border border-[#DDE7F1] px-3 py-2.5 text-sm font-semibold text-[#0A1628] outline-none focus:border-[#009CA4] disabled:bg-slate-50 disabled:text-slate-400",
        };
        return (
          <label key={field.id} htmlFor={common.id} className="flex flex-col gap-1.5 text-sm font-bold text-[#334155]">
            {field.label}
            {field.type === "textarea" ? (
              <textarea {...common} rows={3} className={`${common.className} resize-none`} />
            ) : (
              <input {...common} type={field.type === "date" ? "date" : "text"} />
            )}
          </label>
        );
      })}
    </div>
  );
}
