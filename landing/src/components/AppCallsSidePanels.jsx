function SkeletonLine({ height = 72, radius = 12 }) {
  return (
    <div
      style={{
        height,
        borderRadius: radius,
        background: "linear-gradient(90deg, #eef2f7 25%, #e6ebf2 50%, #eef2f7 75%)",
        backgroundSize: "200% 100%",
        animation: "uwi-calls-shimmer 1.35s infinite linear",
      }}
    />
  );
}

export default function AppCallsSidePanels({
  theme,
  handoffItems,
  handoffsLoading,
  handoffStatusFilter,
  setHandoffStatusFilter,
  handoffTargetFilter,
  setHandoffTargetFilter,
  handoffSearch,
  setHandoffSearch,
  handoffNoteDrafts,
  setHandoffNoteDrafts,
  handoffActionLoading,
  onSaveHandoffNotes,
  onMarkHandoffProcessed,
  onOpenCall,
  stats,
  normalizedCalls,
  urgentItems,
  onRecall,
}) {
  const T = theme;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div style={{ background: T.card, border: `1px solid ${T.border}`, borderRadius: "16px", padding: "18px", boxShadow: "0 1px 3px rgba(0,0,0,0.04)" }}>
        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 10, marginBottom: "10px" }}>
          <div>
            <div style={{ fontSize: "15px", fontWeight: 800, color: T.text, marginBottom: "2px" }}>Transferts humains</div>
            <div style={{ fontSize: "12px", color: T.textFaint }}>Demandes a reprendre par le cabinet</div>
          </div>
          <span style={{ fontSize: 10, fontWeight: 800, color: T.textSoft, background: T.bg, border: `1px solid ${T.border}`, borderRadius: 999, padding: "4px 8px" }}>
            {handoffItems.length}
          </span>
        </div>

        <div style={{ display: "grid", gap: 8, marginBottom: 14 }}>
          <div style={{ display: "flex", gap: 8 }}>
            {[
              ["open", "En attente"],
              ["processed", "Traites"],
              ["cancelled", "Annules"],
            ].map(([value, label]) => (
              <button
                key={value}
                type="button"
                onClick={() => setHandoffStatusFilter(value)}
                style={{
                  flex: 1,
                  padding: "7px 8px",
                  fontSize: 11,
                  fontWeight: 700,
                  borderRadius: 8,
                  border: `1px solid ${handoffStatusFilter === value ? T.tealBorder : T.border}`,
                  background: handoffStatusFilter === value ? T.tealLight : "#fff",
                  color: handoffStatusFilter === value ? T.tealDark : T.textSoft,
                  cursor: "pointer",
                }}
              >
                {label}
              </button>
            ))}
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <select
              value={handoffTargetFilter}
              onChange={(event) => setHandoffTargetFilter(event.target.value)}
              style={{ flex: 1, borderRadius: 8, border: `1px solid ${T.border}`, background: "#fff", color: T.textMid, fontSize: 12, padding: "8px 10px", outline: "none" }}
            >
              <option value="all">Toutes cibles</option>
              <option value="assistant">Assistante</option>
              <option value="practitioner">Praticien</option>
            </select>
            <input
              value={handoffSearch}
              onChange={(event) => setHandoffSearch(event.target.value)}
              placeholder="Patient, resume, ID..."
              style={{ flex: 1.2, borderRadius: 8, border: `1px solid ${T.border}`, background: "#fff", color: T.textMid, fontSize: 12, padding: "8px 10px", outline: "none" }}
            />
          </div>
        </div>

        {handoffsLoading ? (
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {[1, 2, 3].map((item) => <SkeletonLine key={item} height={72} radius={12} />)}
          </div>
        ) : handoffItems.length > 0 ? (
          handoffItems.map((item, index) => (
            <div key={item.id || index} style={{ display: "flex", gap: "10px", padding: "12px 0", borderBottom: index < handoffItems.length - 1 ? `1px solid ${T.borderLight}` : "none" }}>
              <div style={{ width: 42, height: 42, borderRadius: 12, background: item.priority.bg, border: `1px solid ${item.priority.border}`, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 18, flexShrink: 0 }}>
                {item.target === "Praticien" ? "🩺" : "📞"}
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: "13px", fontWeight: 700, color: T.text, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{item.name}</div>
                <div style={{ fontSize: "11px", color: T.textFaint, marginTop: "2px" }}>{item.phone}</div>
                <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 6, marginBottom: 6 }}>
                  <span style={{ fontSize: 10, fontWeight: 700, color: item.priority.color, background: item.priority.bg, border: `1px solid ${item.priority.border}`, borderRadius: 999, padding: "2px 8px" }}>
                    {item.priority.label}
                  </span>
                  <span style={{ fontSize: 10, fontWeight: 700, color: T.purple, background: T.purpleLight, border: `1px solid ${T.purpleBorder}`, borderRadius: 999, padding: "2px 8px" }}>
                    {item.target}
                  </span>
                  <span style={{ fontSize: 10, fontWeight: 700, color: item.status.color, background: item.status.bg, border: `1px solid ${item.status.border}`, borderRadius: 999, padding: "2px 8px" }}>
                    {item.status.label}
                  </span>
                </div>
                <div style={{ fontSize: "11px", color: T.textSoft, lineHeight: 1.45 }}>{item.summary}</div>
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 8, marginBottom: 8 }}>
                  {item.callId ? (
                    <button
                      type="button"
                      onClick={() => onOpenCall(item.callId)}
                      style={{ fontSize: 11, fontWeight: 700, color: T.blue, background: T.blueLight, border: `1px solid ${T.blueBorder}`, borderRadius: 8, padding: "5px 9px", cursor: "pointer" }}
                    >
                      Ouvrir l'appel
                    </button>
                  ) : null}
                  <span style={{ fontSize: 10, color: T.textFaint }}>
                    {item.mode === "live_then_callback" ? "Live puis rappel" : "Rappel uniquement"}
                  </span>
                </div>
                <textarea
                  value={handoffNoteDrafts[String(item.id)] ?? item.notes}
                  onChange={(event) => setHandoffNoteDrafts((prev) => ({ ...prev, [String(item.id)]: event.target.value }))}
                  placeholder="Ajouter une note interne pour le cabinet"
                  style={{ width: "100%", minHeight: 62, resize: "vertical", borderRadius: 10, border: `1px solid ${T.border}`, background: "#fff", color: T.textMid, fontSize: 12, padding: "8px 10px", outline: "none", boxSizing: "border-box" }}
                />
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 6, alignItems: "flex-end", flexShrink: 0 }}>
                {item.dialablePhone ? (
                  <a href={`tel:${item.dialablePhone}`} style={{ fontSize: 11, fontWeight: 700, color: T.tealDark, background: T.tealLight, border: `1px solid ${T.tealBorder}`, borderRadius: 8, padding: "6px 10px", textDecoration: "none" }}>
                    Appeler
                  </a>
                ) : null}
                <button
                  type="button"
                  onClick={() => onSaveHandoffNotes(item.id)}
                  disabled={handoffActionLoading === `notes-${item.id}`}
                  style={{ fontSize: 11, fontWeight: 700, color: T.textSoft, background: "#fff", border: `1px solid ${T.border}`, borderRadius: 8, padding: "6px 10px", cursor: "pointer" }}
                >
                  {handoffActionLoading === `notes-${item.id}` ? "..." : "Sauver note"}
                </button>
                {item.status.label !== "Traite" ? (
                  <button
                    type="button"
                    onClick={() => onMarkHandoffProcessed(item.id)}
                    disabled={handoffActionLoading === String(item.id)}
                    style={{ fontSize: 11, fontWeight: 700, color: T.textSoft, background: "#fff", border: `1px solid ${T.border}`, borderRadius: 8, padding: "6px 10px", cursor: "pointer" }}
                  >
                    {handoffActionLoading === String(item.id) ? "..." : "Traite"}
                  </button>
                ) : null}
              </div>
            </div>
          ))
        ) : (
          <div style={{ fontSize: "12px", color: T.textFaint, lineHeight: 1.5 }}>
            Aucun transfert humain en attente pour le moment.
          </div>
        )}
      </div>

      <div style={{ background: T.purpleLight, border: `1px solid ${T.purpleBorder}`, borderRadius: "16px", padding: "16px 18px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "12px" }}>
          <span style={{ fontSize: "17px" }}>🤖</span>
          <div style={{ fontSize: "14px", fontWeight: 800, color: T.purple }}>Resume UWI du jour</div>
        </div>
        {[
          { icon: "📞", label: "Appels traites", value: `${normalizedCalls.length}` },
          { icon: "📅", label: "RDV detectes", value: `${stats.totalRdv}` },
          { icon: "✅", label: "Taux de resolution", value: `${stats.resolvedRate}%` },
          { icon: "⏱", label: "Duree moy.", value: stats.durationAverage ? `${stats.durationAverage} min` : "-" },
        ].map((row, index) => (
          <div key={row.label} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "7px 0", borderBottom: index < 3 ? `1px solid ${T.purpleBorder}` : "none" }}>
            <span style={{ fontSize: "12px", color: T.purple }}>{row.icon} {row.label}</span>
            <span style={{ fontSize: "13px", fontWeight: 700, color: T.purple }}>{row.value}</span>
          </div>
        ))}
        <div style={{ marginTop: 12, fontSize: 11, lineHeight: 1.55, color: T.purple }}>
          UWI absorbe la majorite des demandes simples et remonte surtout les urgences, rappels et cas non resolus.
        </div>
      </div>

      {urgentItems.length > 0 ? (
        <div style={{ background: T.redLight, border: `1px solid ${T.redBorder}`, borderRadius: "16px", padding: "15px 17px" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10, marginBottom: "10px" }}>
            <div style={{ fontSize: "13px", fontWeight: 800, color: T.red }}>⚠ Rappels urgents</div>
            <span style={{ fontSize: 10, fontWeight: 800, color: T.red, background: "#fff", border: `1px solid ${T.redBorder}`, borderRadius: 999, padding: "3px 8px" }}>
              {urgentItems.length} priorite{urgentItems.length > 1 ? "s" : ""}
            </span>
          </div>
          {urgentItems.map((call, index) => (
            <div key={call.id} style={{ display: "flex", alignItems: "center", gap: "10px", padding: "8px 0", borderBottom: index < urgentItems.length - 1 ? "1px solid #FCA5A5" : "none" }}>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: "12px", fontWeight: 700, color: T.red }}>{call.name}</div>
                <div style={{ fontSize: "11px", color: "#ef9999" }}>{call.phone}</div>
              </div>
              <button type="button" onClick={() => onRecall(call)} style={{ fontSize: "11px", fontWeight: 700, color: "#fff", background: T.red, border: "none", borderRadius: "7px", padding: "4px 10px", cursor: "pointer" }}>
                Rappeler
              </button>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}
