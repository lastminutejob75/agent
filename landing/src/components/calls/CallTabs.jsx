export default function CallTabs({ activeTab, onChange, toProcessCount, unknownCount }) {
  const tabs = [
    ["tous", "Tous", null],
    ["a-traiter", "À traiter", toProcessCount],
    ["rendez-vous", "Rendez-vous", null],
    ["sans-fiche", "Sans fiche patient", unknownCount],
    ["historique", "Historique", null],
  ];

  return (
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div className="flex flex-wrap gap-2">
        {tabs.map(([key, label, count]) => (
          <button
            key={key}
            type="button"
            onClick={() => onChange(key)}
            className={`inline-flex items-center gap-2 rounded-xl border px-4 py-2 text-sm font-extrabold transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#009CA4] focus-visible:ring-offset-1 ${
              activeTab === key
                ? "border-[#009CA4] bg-[#E6F7F8] text-[#007F87]"
                : "border-[#E2E8F0] bg-white text-[#334155] hover:bg-slate-50"
            }`}
          >
            {label}
            {Number.isFinite(count) ? (
              <span className="rounded-full bg-[#FFF3EA] px-2 py-0.5 text-xs font-black text-[#C2410C]">
                {count}
              </span>
            ) : null}
          </button>
        ))}
      </div>
    </div>
  );
}
