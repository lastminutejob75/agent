import { Link } from "react-router-dom";
import {
  formatPatientDuplicateConflict,
  hasBlockingPatientDuplicate,
  patientDuplicateDashboardUrl,
} from "../../lib/patientDuplicateCheck";

export default function PatientDuplicateBanner({ conflicts, className = "" }) {
  const items = Array.isArray(conflicts) ? conflicts.filter(Boolean) : [];
  if (!items.length) return null;

  const blocking = hasBlockingPatientDuplicate(items);
  const borderClass = blocking ? "border-red-200 bg-red-50 text-red-950" : "border-amber-200 bg-amber-50 text-amber-950";
  const title = blocking
    ? "Doublon détecté — enregistrement bloqué"
    : "Une fiche existe déjà pour ce numéro";

  return (
    <div className={`rounded-xl border px-3 py-2.5 text-xs font-semibold leading-snug ${borderClass} ${className}`.trim()}>
      <p className="m-0 font-black">{title}</p>
      <ul className="mt-2 list-none space-y-2 p-0">
        {items.map((conflict) => {
          const key = `${conflict.field || "unknown"}-${conflict.phone || conflict.email || conflict.display_name || "x"}`;
          return (
            <li key={key} className="m-0">
              <p className="m-0">{formatPatientDuplicateConflict(conflict)}</p>
              {conflict.phone ? (
                <Link
                  to={patientDuplicateDashboardUrl(conflict)}
                  className="mt-1 inline-block font-black underline underline-offset-2 hover:opacity-80"
                >
                  Ouvrir la fiche existante
                </Link>
              ) : null}
            </li>
          );
        })}
      </ul>
      {!blocking ? (
        <p className="mb-0 mt-2 opacity-90">
          En validant, vous enrichissez la fiche existante pour ce numéro.
        </p>
      ) : null}
    </div>
  );
}
