import { useState, useEffect } from "react";
import { useNavigate, useOutletContext } from "react-router-dom";
import { api } from "../lib/api.js";

const COUNTERS_DEFAULT = { calls_total: 0, bookings_confirmed: 0, transfers: 0, abandons: 0 };

function formatTime(ts) {
  if (ts == null) return "—";
  try {
    const d = typeof ts === "string" ? new Date(ts.replace("Z", "+00:00")) : new Date(ts);
    return d.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
  } catch {
    return "—";
  }
}

function formatDuration() {
  return "—";
}

function outcomeTag(outcome) {
  if (outcome === "booking_confirmed") return { label: "✓ RDV confirmé", cls: "cd-tg-g" };
  if (outcome === "transferred_human") return { label: "Transféré", cls: "cd-tg-n" };
  if (outcome === "user_abandon") return { label: "Abandon", cls: "cd-tg-n" };
  return { label: "Appel traité", cls: "cd-tg-n" };
}

function outcomeDot(outcome) {
  if (outcome === "booking_confirmed") return "cd-cd-g";
  if (outcome === "transferred_human") return "cd-cd-o";
  return "cd-cd-o";
}

export default function AppDashboard() {
  const navigate = useNavigate();
  const { me, dashboard } = useOutletContext() || {};
  const [kpis, setKpis] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api.tenantKpis(7).then(setKpis).catch(() => setKpis(null));
  }, []);

  const go = (path) => () => navigate(path);
  const counters = { ...COUNTERS_DEFAULT, ...(dashboard?.counters_7d || {}) };
  const lastCall = dashboard?.last_call;
  const lastBooking = dashboard?.last_booking;
  const today = new Date();
  const dayLabel = today.toLocaleDateString("fr-FR", { weekday: "long", day: "numeric", month: "long" });
  const weekDays = [];
  for (let i = -2; i <= 2; i++) {
    const d = new Date(today);
    d.setDate(d.getDate() + i);
    weekDays.push({
      label: d.toLocaleDateString("fr-FR", { weekday: "short" }).slice(0, 1),
      num: d.getDate(),
      today: i === 0,
      date: d,
    });
  }
  const rdvPlaceholder = [
    { time: "09h", name: "Claire Fontaine", motif: "Consultation", src: "uwi" },
    { time: "10h", name: "Marie Dupont", motif: "Tension artérielle", src: "uwi" },
    { time: "11h", name: "Henri Blanc", motif: "Renouvellement", src: "doc" },
    { time: "14h", name: "Isabelle Roy", motif: "Bilan annuel", src: "doc" },
  ];

  const callRows = [];
  if (lastCall) {
    const tag = outcomeTag(lastCall.outcome);
    callRows.push({
      id: "last-call",
      time: formatTime(lastCall.created_at),
      duration: formatDuration(),
      name: lastCall.name || "Patient",
      agentName: "UWi",
      text: lastCall.slot_label
        ? `RDV pris ${lastCall.slot_label}`
        : lastCall.outcome === "booking_confirmed"
          ? "RDV confirmé"
          : lastCall.outcome === "transferred_human"
            ? "Appel transféré à un humain"
            : "Appel traité",
      tag: tag.label,
      tagCls: tag.cls,
      dot: outcomeDot(lastCall.outcome),
      urg: false,
    });
  }
  if (callRows.length === 0) {
    callRows.push({
      id: "empty",
      time: "—",
      duration: "—",
      name: "Aucun appel récent",
      agentName: null,
      text: "Les appels traités par UWi apparaîtront ici.",
      tag: "Info",
      tagCls: "cd-tg-n",
      dot: "cd-cd-g",
      urg: false,
    });
  }

  const decrochePct = counters.calls_total > 0 ? Math.min(100, Math.round((counters.bookings_confirmed + counters.transfers) / counters.calls_total * 100)) : 98;
  const minutesUsed = 563;
  const minutesIncluded = 800;
  const rdvAuj = counters.bookings_confirmed ?? 0;

  return (
    <div className="client-dash" style={{ display: "flex", flexDirection: "column", gap: 26 }}>
      {/* Greeting */}
      <div className="client-dash cd-greeting">
        <div className="client-dash cd-gr-l">
          <div className="client-dash cd-gr-hello">
            Bonjour, {me?.tenant_name?.split(/\s+/)[0] || "Cabinet"} 👋
          </div>
          <div className="client-dash cd-gr-sub">
            {dayLabel} · <strong>UWi</strong> a traité {counters.calls_total} appel{counters.calls_total !== 1 ? "s" : ""} sur les 7 derniers jours
            {counters.bookings_confirmed > 0 && <> · <strong>{counters.bookings_confirmed} RDV</strong> pris</>}
          </div>
        </div>
        <div className="client-dash cd-gr-kpis">
          <div className="client-dash cd-gr-kpi">
            <div className="client-dash cd-gr-kpi-val">{decrochePct}%</div>
            <div className="client-dash cd-gr-kpi-lbl">Décroché</div>
          </div>
          <div className="client-dash cd-gr-kpi">
            <div className="client-dash cd-gr-kpi-val">{minutesUsed}</div>
            <div className="client-dash cd-gr-kpi-lbl">Min / {minutesIncluded}</div>
          </div>
          <div className="client-dash cd-gr-kpi">
            <div className="client-dash cd-gr-kpi-val">{rdvAuj}</div>
            <div className="client-dash cd-gr-kpi-lbl">RDV (7j)</div>
          </div>
        </div>
      </div>

      <div className="client-dash cd-layout">
        <div className="client-dash cd-lstack">
          {/* Actions requises */}
          <div className="client-dash cd-card">
            <div className="client-dash cd-ch">
              <div className="client-dash cd-ch-left">
                <div className="client-dash cd-ch-ico cd-ico-r">🚨</div>
                <div>
                  <div className="client-dash cd-ch-title">Actions requises</div>
                  <div className="client-dash cd-ch-sub">Nécessitent votre attention aujourd'hui</div>
                </div>
              </div>
              <a className="client-dash cd-ch-lnk" href="/app/actions" onClick={(e) => { e.preventDefault(); navigate("/app/actions"); }}>Tout voir →</a>
            </div>
            <div className="client-dash cd-urg-grid">
              <div className="client-dash cd-urg-cell" onClick={go("/app/actions")}>
                <div className="client-dash cd-urg-bubble cd-ub-r">📞</div>
                <div>
                  <div className="client-dash cd-urg-count cd-uc-r">0</div>
                  <div className="client-dash cd-urg-lbl">Rappels en attente</div>
                  <div className="client-dash cd-urg-cta">Appeler maintenant →</div>
                </div>
              </div>
              <div className="client-dash cd-urg-cell" onClick={go("/app/actions")}>
                <div className="client-dash cd-urg-bubble cd-ub-o">💊</div>
                <div>
                  <div className="client-dash cd-urg-count cd-uc-o">0</div>
                  <div className="client-dash cd-urg-lbl">Ordonnance à valider</div>
                  <div className="client-dash cd-urg-cta">Valider →</div>
                </div>
              </div>
            </div>
          </div>

          {/* Appels d'aujourd'hui */}
          <div className="client-dash cd-card">
            <div className="client-dash cd-ch">
              <div className="client-dash cd-ch-left">
                <div className="client-dash cd-ch-ico cd-ico-t">📋</div>
                <div>
                  <div className="client-dash cd-ch-title">Appels récents</div>
                  <div className="client-dash cd-ch-sub">{counters.calls_total} appels (7j)</div>
                </div>
              </div>
              <a className="client-dash cd-ch-lnk" href="/app/appels" onClick={(e) => { e.preventDefault(); navigate("/app/appels"); }}>Historique →</a>
            </div>
            <div className="client-dash cd-call-list">
              {callRows.map((row) => (
                <div key={row.id} className={`client-dash cd-call-row ${row.urg ? "cd-call-urg" : ""}`}>
                  <div className="client-dash cd-ctime">
                    <span className="client-dash cd-ct-h">{row.time}</span>
                    <span className="client-dash cd-ct-d">{row.duration}</span>
                  </div>
                  <div className={`client-dash cd-cdot ${row.dot}`} />
                  <div className="client-dash cd-cbody">
                    <div className="client-dash cd-cname">
                      {row.name}
                      {row.agentName && <span className="client-dash cd-agent-badge">{row.agentName}</span>}
                    </div>
                    <div className="client-dash cd-ctext">{row.text}</div>
                    <span className={`client-dash cd-ctag ${row.tagCls}`}>{row.tag}</span>
                  </div>
                  <div className="client-dash cd-cbtns">
                    <button type="button" className="client-dash cd-cbtn cd-btn-view" onClick={go("/app/appels")}>Transcription</button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Colonne droite */}
        <div className="client-dash cd-rstack">
          {/* Agenda */}
          <div className="client-dash cd-card">
            <div className="client-dash cd-ch">
              <div className="client-dash cd-ch-left">
                <div className="client-dash cd-ch-ico cd-ico-t">📆</div>
                <div><div className="client-dash cd-ch-title">Planning du jour</div></div>
              </div>
              <a className="client-dash cd-ch-lnk" href="/app/agenda" onClick={(e) => { e.preventDefault(); navigate("/app/agenda"); }}>Agenda →</a>
            </div>
            <div className="client-dash cd-week-strip">
              {weekDays.map((w) => (
                <div key={w.num} className={`client-dash cd-wday ${w.today ? "wt" : ""}`}>
                  <span className="client-dash cd-wl">{w.label}</span>
                  <span className="client-dash cd-wn">{w.num}</span>
                  <div className="client-dash cd-wpip" />
                </div>
              ))}
            </div>
            <div className="client-dash cd-rdv-list">
              {rdvPlaceholder.map((r) => (
                <div key={r.time + r.name} className="client-dash cd-rdv-item">
                  <span className="client-dash cd-rdv-t">{r.time}</span>
                  <div className="client-dash cd-rdv-bar" />
                  <div style={{ flex: 1 }}>
                    <div className="client-dash cd-rdv-nm">{r.name}</div>
                    <div className="client-dash cd-rdv-m">{r.motif}</div>
                  </div>
                  <span className={`client-dash cd-rdv-src ${r.src === "uwi" ? "cd-rs-uwi" : "cd-rs-doc"}`}>{r.src === "uwi" ? "UWi" : "Doctolib"}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Stats */}
          <div className="client-dash cd-card">
            <div className="client-dash cd-ch">
              <div className="client-dash cd-ch-left">
                <div className="client-dash cd-ch-ico cd-ico-t">📊</div>
                <div><div className="client-dash cd-ch-title">{today.toLocaleDateString("fr-FR", { month: "long", year: "numeric" })}</div></div>
              </div>
            </div>
            <div className="client-dash cd-stat-grid">
              <div className="client-dash cd-stat-cell">
                <div className="client-dash cd-st-lbl">Appels</div>
                <div className="client-dash cd-st-val">{counters.calls_total}</div>
                <div className="client-dash cd-st-sub">{kpis?.trend?.calls_pct != null ? `+${kpis.trend.calls_pct}% vs sem. préc.` : "7 derniers jours"}</div>
              </div>
              <div className="client-dash cd-stat-cell">
                <div className="client-dash cd-st-lbl">Décroché</div>
                <div className="client-dash cd-st-val cd-st-t">{decrochePct}%</div>
                <div className="client-dash cd-st-sub">par UWi</div>
              </div>
              <div className="client-dash cd-stat-cell">
                <div className="client-dash cd-st-lbl">RDV pris</div>
                <div className="client-dash cd-st-val">{counters.bookings_confirmed}</div>
                <div className="client-dash cd-st-sub">via UWi</div>
              </div>
              <div className="client-dash cd-stat-cell">
                <div className="client-dash cd-st-lbl">Transferts</div>
                <div className="client-dash cd-st-val">{counters.transfers}</div>
                <div className="client-dash cd-st-sub">vers humain</div>
              </div>
            </div>
          </div>

          {/* Facturation */}
          <div className="client-dash cd-card">
            <div className="client-dash cd-ch">
              <div className="client-dash cd-ch-left">
                <div className="client-dash cd-ch-ico cd-ico-t">💳</div>
                <div><div className="client-dash cd-ch-title">Forfait Growth</div></div>
              </div>
              <a className="client-dash cd-ch-lnk" href="/app/facturation" onClick={(e) => { e.preventDefault(); navigate("/app/facturation"); }}>Détail →</a>
            </div>
            <div className="client-dash cd-bill-body">
              <div className="client-dash cd-bill-top">
                <div>
                  <div className="client-dash cd-bill-lbl">Ce mois</div>
                  <div className="client-dash cd-bill-val">149 <span style={{ fontSize: 14, fontWeight: 600, color: "var(--muted)" }}>€</span></div>
                  <div className="client-dash cd-bill-sub">Renouvellement le 1er</div>
                </div>
                <div className="client-dash cd-bill-ok">✓ Dans le forfait</div>
              </div>
              <div>
                <div className="client-dash cd-bill-row">
                  <span className="client-dash cd-bill-row-lbl">Minutes utilisées</span>
                  <span className="client-dash cd-bill-row-val">{minutesUsed} / {minutesIncluded}</span>
                </div>
                <div className="client-dash cd-bill-bar">
                  <div className="client-dash cd-bill-fill" style={{ width: `${Math.min(100, (minutesUsed / minutesIncluded) * 100)}%` }} />
                </div>
                <div className="client-dash cd-bill-hint">{minutesIncluded - minutesUsed} min restantes · pas de dépassement prévu</div>
              </div>
              <button type="button" className="client-dash cd-bill-cta" onClick={go("/app/facturation")}>Voir la facturation complète</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
