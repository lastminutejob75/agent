import { useState, useEffect, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  getTenant,
  getTenantDashboard,
  getTenantActivity,
  getTenantCalls,
  getCallDetail,
  getTenantInvoices,
  getTenantUsage,
  getTenantQuota,
  getTenantFaq,
  resetTenantFaq,
  updateTenantFlags,
  updateTenantFaq,
  updateTenantHoraires,
  updateTenantParams,
  sendPaymentLink,
  sendTenantOnboardingLink,
} from "../../lib/adminApi";
import { deriveHorairesText, normalizeBookingRules } from "../../lib/bookingUtils.js";
import FaqEditor from "../../components/FaqEditor.jsx";

const C = {
  bg: "#0A1828",
  surface: "#0F2236",
  card: "#132840",
  border: "#1E3D56",
  accent: "#00E5A0",
  accentDim: "#00b87c",
  blue: "#5BA8FF",
  text: "#FFFFFF",
  muted: "#6B90A8",
  danger: "#FF6B6B",
  warning: "#FFB347",
};

const TABS = [
  { id: "info", label: "Infos", icon: "🏥" },
  { id: "timeline", label: "Timeline", icon: "📋" },
  { id: "calls", label: "Appels", icon: "📞" },
  { id: "invoices", label: "Factures", icon: "💳" },
  { id: "quota", label: "Quota", icon: "📊" },
  { id: "faq", label: "FAQ", icon: "💬" },
  { id: "actions", label: "Actions", icon: "⚙️" },
];

function ServiceStatusBadge({ status }) {
  const map = {
    online: { color: C.accent, label: "En ligne" },
    offline: { color: C.danger, label: "Hors ligne" },
    unknown: { color: C.muted, label: "Inconnu" },
  };
  const s = map[status] || map.unknown;
  return (
    <span style={{ display: "flex", alignItems: "center", gap: 5, fontSize: 12, color: s.color, fontWeight: 600 }}>
      <span style={{ width: 6, height: 6, borderRadius: "50%", background: s.color, animation: "uwi-pulse 2s ease infinite", display: "inline-block" }} />
      {s.label}
    </span>
  );
}

function InfoCard({ title, children }) {
  return (
    <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 16, padding: 20 }}>
      <div style={{ fontSize: 13, fontWeight: 700, color: C.text, marginBottom: 14 }}>{title}</div>
      {children}
    </div>
  );
}

function InfoRow({ label, value }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
      <span style={{ fontSize: 12, color: C.muted }}>{label}</span>
      <span style={{ fontSize: 12, fontWeight: 600, color: C.text, fontFamily: "monospace", maxWidth: "60%", textAlign: "right", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{value ?? "—"}</span>
    </div>
  );
}

function Spinner() {
  return (
    <div style={{ color: C.muted, fontSize: 13, padding: "20px 0" }}>Chargement…</div>
  );
}

function Empty({ text }) {
  return (
    <div style={{ color: C.muted, fontSize: 13, padding: "20px 0", textAlign: "center" }}>{text}</div>
  );
}

function PageLoader() {
  return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "center", minHeight: 200, color: C.muted }}>
      Chargement…
    </div>
  );
}

function PageError({ msg, onRetry }) {
  return (
    <div style={{ padding: 24, background: "rgba(255,107,107,0.1)", border: `1px solid ${C.danger}40`, borderRadius: 12, color: C.danger }}>
      ⚠️ {msg}
      {onRetry && (
        <button type="button" onClick={onRetry} style={{ marginLeft: 12, padding: "6px 12px", background: "transparent", border: `1px solid ${C.danger}`, borderRadius: 8, color: C.danger, cursor: "pointer", fontWeight: 600 }}>
          Réessayer
        </button>
      )}
    </div>
  );
}

function TabInfo({ tenant, dashboard }) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
      <InfoCard title="Informations générales">
        {[
          ["Nom", tenant?.name],
          ["Timezone", tenant?.timezone || "Europe/Paris"],
          ["Statut", tenant?.status],
          ["Créé le", tenant?.created_at ? new Date(tenant.created_at).toLocaleDateString("fr-FR") : "—"],
        ].map(([l, v]) => (
          <InfoRow key={l} label={l} value={v} />
        ))}
      </InfoCard>

      <InfoCard title="Dernier appel">
        {dashboard?.last_call ? (
          <>
            <InfoRow label="Date" value={new Date(dashboard.last_call.created_at).toLocaleString("fr-FR")} />
            <InfoRow label="Résultat" value={dashboard.last_call.outcome} />
            {dashboard.last_call.motif && <InfoRow label="Motif" value={dashboard.last_call.motif} />}
            {dashboard.last_call.name && <InfoRow label="Patient" value={dashboard.last_call.name} />}
          </>
        ) : (
          <div style={{ color: C.muted, fontSize: 13 }}>Aucun appel enregistré</div>
        )}
      </InfoCard>

      <InfoCard title="Dernier RDV confirmé">
        {dashboard?.last_booking ? (
          <>
            <InfoRow label="Patient" value={dashboard.last_booking.name} />
            <InfoRow label="Créneau" value={dashboard.last_booking.slot_label} />
            <InfoRow label="Source" value={dashboard.last_booking.source} />
          </>
        ) : (
          <div style={{ color: C.muted, fontSize: 13 }}>Aucun RDV enregistré</div>
        )}
      </InfoCard>

      <InfoCard title="Raisons de transfert">
        {dashboard?.transfer_reasons?.top_transferred?.length ? (
          dashboard.transfer_reasons.top_transferred.map((r) => (
            <InfoRow key={r.reason} label={r.reason} value={`${r.count}×`} />
          ))
        ) : (
          <div style={{ color: C.muted, fontSize: 13 }}>Aucun transfert</div>
        )}
      </InfoCard>
    </div>
  );
}

function TabTimeline({ tenantId }) {
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getTenantActivity(tenantId, 30)
      .then((r) => setEvents(r?.items || r || []))
      .finally(() => setLoading(false));
  }, [tenantId]);

  const EVENT_COLORS = {
    booking_confirmed: C.accent,
    transferred_human: C.warning,
    transferred: C.warning,
    user_abandon: C.danger,
    abandon: C.danger,
    anti_loop_trigger: C.danger,
  };

  return (
    <div style={{ maxWidth: 640 }}>
      {loading ? (
        <Spinner />
      ) : events.length === 0 ? (
        <Empty text="Aucune activité sur la période" />
      ) : (
        events.map((e, i) => (
          <div key={i} style={{ display: "flex", gap: 14, marginBottom: 16, alignItems: "flex-start" }}>
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", flexShrink: 0 }}>
              <div style={{ width: 10, height: 10, borderRadius: "50%", background: EVENT_COLORS[e.event] || C.blue, marginTop: 3 }} />
              {i < events.length - 1 && <div style={{ width: 1, flex: 1, background: C.border, marginTop: 4, minHeight: 20 }} />}
            </div>
            <div style={{ flex: 1, background: C.card, border: `1px solid ${C.border}`, borderRadius: 10, padding: "10px 14px" }}>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 3 }}>
                <span style={{ fontSize: 13, fontWeight: 700, color: EVENT_COLORS[e.event] || C.text }}>{e.event}</span>
                <span style={{ fontSize: 11, color: C.muted }}>{new Date(e.date || e.created_at).toLocaleString("fr-FR")}</span>
              </div>
              {e.meta && <div style={{ fontSize: 11, color: C.muted, fontFamily: "monospace" }}>{JSON.stringify(e.meta)}</div>}
            </div>
          </div>
        ))
      )}
    </div>
  );
}

function TabCalls({ tenantId }) {
  const [calls, setCalls] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState(null);
  const [detail, setDetail] = useState(null);
  const [loadDetail, setLoadDetail] = useState(false);

  useEffect(() => {
    getTenantCalls(tenantId, 7, 20)
      .then((r) => setCalls(r?.items || []))
      .finally(() => setLoading(false));
  }, [tenantId]);

  const openCall = async (call) => {
    setSelected(call);
    setLoadDetail(true);
    try {
      const d = await getCallDetail(tenantId, call.call_id);
      setDetail(d);
    } finally {
      setLoadDetail(false);
    }
  };

  const RESULT_MAP = {
    booking_confirmed: { label: "RDV", color: C.accent },
    transferred_human: { label: "Transfert", color: C.warning },
    transferred: { label: "Transfert", color: C.warning },
    user_abandon: { label: "Abandon", color: C.danger },
    abandon: { label: "Abandon", color: C.danger },
    error: { label: "Erreur", color: C.danger },
  };

  return (
    <div style={{ display: "grid", gridTemplateColumns: selected ? "1fr 1fr" : "1fr", gap: 14 }}>
      <div>
        {loading ? (
          <Spinner />
        ) : calls.length === 0 ? (
          <Empty text="Aucun appel sur les 7 derniers jours" />
        ) : (
          calls.map((c) => {
            const res = RESULT_MAP[c.result] || { label: "Info", color: C.blue };
            return (
              <div
                key={c.call_id}
                onClick={() => openCall(c)}
                style={{
                  background: selected?.call_id === c.call_id ? "rgba(0,229,160,0.05)" : C.card,
                  border: `1px solid ${selected?.call_id === c.call_id ? C.accent : C.border}`,
                  borderRadius: 12,
                  padding: "12px 16px",
                  marginBottom: 8,
                  cursor: "pointer",
                  transition: "all 0.15s",
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                }}
              >
                <div>
                  <div style={{ fontSize: 13, fontWeight: 600, color: C.text, marginBottom: 3 }}>
                    {new Date(c.started_at || c.last_event_at).toLocaleString("fr-FR")}
                  </div>
                  <div style={{ fontSize: 11, color: C.muted, fontFamily: "monospace" }}>{c.call_id?.slice(0, 20)}…</div>
                </div>
                <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
                  {c.duration_min != null && <span style={{ fontSize: 12, color: C.muted }}>{c.duration_min}m</span>}
                  <span style={{ background: `${res.color}18`, color: res.color, border: `1px solid ${res.color}40`, borderRadius: 6, padding: "2px 8px", fontSize: 11, fontWeight: 700 }}>{res.label}</span>
                </div>
              </div>
            );
          })
        )}
      </div>

      {selected && (
        <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 16, padding: 20, position: "sticky", top: 0, maxHeight: "80vh", overflowY: "auto" }}>
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 16 }}>
            <div style={{ fontSize: 14, fontWeight: 700, color: C.text }}>Détail appel</div>
            <button
              type="button"
              onClick={() => {
                setSelected(null);
                setDetail(null);
              }}
              style={{ background: "transparent", border: "none", color: C.muted, cursor: "pointer", fontSize: 16 }}
            >
              ✕
            </button>
          </div>
          {loadDetail ? (
            <Spinner />
          ) : (
            detail && (
              <>
                <div style={{ marginBottom: 16 }}>
                  <div style={{ fontSize: 11, color: C.muted, fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.8, marginBottom: 10 }}>Événements</div>
                  {detail.events?.map((ev, i) => (
                    <div key={i} style={{ display: "flex", gap: 10, marginBottom: 8, fontSize: 12 }}>
                      <span style={{ color: C.muted, flexShrink: 0 }}>{new Date(ev.created_at).toLocaleTimeString("fr-FR")}</span>
                      <span style={{ color: C.accent, fontWeight: 600 }}>{ev.event}</span>
                    </div>
                  ))}
                </div>
                {detail.transcript && (
                  <div>
                    <div style={{ fontSize: 11, color: C.muted, fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.8, marginBottom: 10 }}>Transcription</div>
                    <div style={{ fontSize: 12, color: C.text, lineHeight: 1.7, whiteSpace: "pre-wrap", background: C.surface, borderRadius: 10, padding: "12px 14px" }}>{detail.transcript}</div>
                  </div>
                )}
              </>
            )
          )}
        </div>
      )}
    </div>
  );
}

function TabInvoices({ tenantId }) {
  const [invoices, setInvoices] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getTenantInvoices(tenantId)
      .then((r) => setInvoices(r?.items || r || []))
      .catch(() => setInvoices([]))
      .finally(() => setLoading(false));
  }, [tenantId]);

  return loading ? (
    <Spinner />
  ) : invoices.length === 0 ? (
    <Empty text="Aucune facture Stripe" />
  ) : (
    <div style={{ maxWidth: 640 }}>
      {invoices.map((inv) => (
        <div
          key={inv.id}
          style={{
            background: C.card,
            border: `1px solid ${C.border}`,
            borderRadius: 12,
            padding: "14px 18px",
            marginBottom: 8,
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
          }}
        >
          <div>
            <div style={{ fontSize: 13, fontWeight: 600, color: C.text, marginBottom: 3 }}>
              {inv.created ? new Date(inv.created * 1000).toLocaleDateString("fr-FR") : "—"}
            </div>
            <div style={{ fontSize: 11, color: C.muted, fontFamily: "monospace" }}>{inv.id}</div>
          </div>
          <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
            <span style={{ fontSize: 15, fontWeight: 800, color: C.text }}>
              {(inv.amount_due ?? 0).toFixed(2)}€
            </span>
            <span
              style={{
                background: inv.status === "paid" ? "rgba(0,229,160,0.12)" : "rgba(255,107,107,0.12)",
                color: inv.status === "paid" ? C.accent : C.danger,
                border: `1px solid ${inv.status === "paid" ? C.accent + "40" : C.danger + "40"}`,
                borderRadius: 6,
                padding: "2px 8px",
                fontSize: 11,
                fontWeight: 700,
              }}
            >
              {inv.status}
            </span>
            {inv.invoice_pdf && (
              <a href={inv.invoice_pdf} target="_blank" rel="noreferrer" style={{ fontSize: 12, color: C.blue, fontWeight: 600 }}>PDF ↗</a>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

function TabQuota({ tenantId }) {
  const [usage, setUsage] = useState(null);
  const [quota, setQuota] = useState(null);
  const [month, setMonth] = useState(() => new Date().toISOString().slice(0, 7));

  useEffect(() => {
    Promise.all([getTenantUsage(tenantId, month), getTenantQuota(tenantId, month)])
      .then(([u, q]) => {
        setUsage(u);
        setQuota(q);
      })
      .catch(() => {});
  }, [tenantId, month]);

  const used = quota?.used_minutes_month ?? quota?.used ?? 0;
  const included = quota?.included_minutes_month ?? quota?.included ?? 0;
  const pct = included > 0 ? Math.min((used / included) * 100, 100) : 0;
  const barColor = pct > 90 ? C.danger : pct > 70 ? C.warning : C.accent;

  return (
    <div style={{ maxWidth: 500 }}>
      <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 20 }}>
        <input
          type="month"
          value={month}
          onChange={(e) => setMonth(e.target.value)}
          style={{
            background: C.card,
            border: `1px solid ${C.border}`,
            borderRadius: 9,
            color: C.text,
            padding: "6px 12px",
            fontSize: 13,
            fontFamily: "inherit",
          }}
        />
      </div>

      <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 16, padding: 22, marginBottom: 14 }}>
        <div style={{ fontSize: 14, fontWeight: 700, color: C.text, marginBottom: 16 }}>Usage Vapi — {month}</div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 20 }}>
          <div style={{ background: C.surface, borderRadius: 10, padding: 14, textAlign: "center" }}>
            <div style={{ fontSize: 28, fontWeight: 800, color: C.accent, letterSpacing: -1 }}>{(usage?.minutes_total ?? usage?.minutes ?? "—").toFixed?.(0) ?? "—"}</div>
            <div style={{ fontSize: 11, color: C.muted, textTransform: "uppercase", letterSpacing: 0.5 }}>Minutes</div>
          </div>
          <div style={{ background: C.surface, borderRadius: 10, padding: 14, textAlign: "center" }}>
            <div style={{ fontSize: 28, fontWeight: 800, color: C.warning, letterSpacing: -1 }}>${(usage?.cost_usd ?? "—").toFixed?.(2) ?? "—"}</div>
            <div style={{ fontSize: 11, color: C.muted, textTransform: "uppercase", letterSpacing: 0.5 }}>Coût Vapi</div>
          </div>
        </div>

        {quota && (
          <>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, color: C.muted, marginBottom: 6 }}>
              <span>{Number(used).toFixed(0)} min utilisées</span>
              <span>{included} min incluses</span>
            </div>
            <div style={{ height: 8, background: C.border, borderRadius: 4, overflow: "hidden", marginBottom: 6 }}>
              <div style={{ width: `${pct}%`, height: "100%", background: barColor, borderRadius: 4, transition: "width 0.6s ease" }} />
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, color: C.muted }}>
              <span style={{ color: barColor, fontWeight: 600 }}>{pct.toFixed(0)}% utilisé</span>
              <span>{Math.max(0, included - used).toFixed(0)} min restantes</span>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function TabActions({ tenantId, tenant, onSaved }) {
  const [flags, setFlags] = useState(tenant?.flags || {});
  const [params, setParams] = useState(tenant?.params || {});
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState(null);
  const [paymentLinkLoading, setPaymentLinkLoading] = useState(false);
  const [paymentLinkUrl, setPaymentLinkUrl] = useState("");
  const [paymentLinkEmail, setPaymentLinkEmail] = useState("");
  const [showOnboardingModal, setShowOnboardingModal] = useState(false);
  const [onboardingEmail, setOnboardingEmail] = useState("");
  const [onboardingLoading, setOnboardingLoading] = useState(false);

  useEffect(() => {
    setFlags(tenant?.flags || {});
    setParams(tenant?.params || {});
    setOnboardingEmail(
      tenant?.contact_email || tenant?.params?.contact_email || tenant?.params?.billing_email || "",
    );
  }, [tenant]);

  const FLAG_KEYS = ["ENABLE_LLM_ASSIST_START", "ENABLE_ANTI_LOOP", "ENABLE_TRANSFER", "ENABLE_BOOKING", "ENABLE_FAQ"];
  const PARAM_KEYS = ["calendar_id", "phone_number", "transfer_number", "timezone", "assistant_name"];
  const bookingRules = normalizeBookingRules(params);
  const horairesPreview = deriveHorairesText(bookingRules);

  const saveFlags = async () => {
    setSaving(true);
    setMsg(null);
    try {
      await updateTenantFlags(tenantId, flags);
      setMsg({ type: "success", text: "Flags sauvegardés ✓" });
      onSaved?.();
    } catch (e) {
      setMsg({ type: "error", text: e?.message || "Erreur" });
    } finally {
      setSaving(false);
    }
  };

  const saveParams = async () => {
    setSaving(true);
    setMsg(null);
    try {
      await updateTenantParams(tenantId, params);
      setMsg({ type: "success", text: "Params sauvegardés ✓" });
      onSaved?.();
    } catch (e) {
      setMsg({ type: "error", text: e?.message || "Erreur" });
    } finally {
      setSaving(false);
    }
  };

  const saveHoraires = async () => {
    setSaving(true);
    setMsg(null);
    try {
      await updateTenantHoraires(tenantId, bookingRules);
      setParams((p) => ({ ...p, horaires: horairesPreview }));
      setMsg({ type: "success", text: `Horaires sauvegardés ✓ ${horairesPreview}` });
      onSaved?.();
    } catch (e) {
      setMsg({ type: "error", text: e?.message || "Erreur horaires" });
    } finally {
      setSaving(false);
    }
  };

  const handleSendPaymentLink = async () => {
    if (!tenantId) return;
    setPaymentLinkLoading(true);
    setMsg(null);
    try {
      const res = await sendPaymentLink(tenantId);
      setPaymentLinkUrl(res?.checkout_url || "");
      setPaymentLinkEmail(res?.email || "");
      setMsg({ type: "success", text: `Lien envoyé à ${res?.email || "ce client"} ✓` });
      onSaved?.();
    } catch (e) {
      setMsg({ type: "error", text: e?.message || "Erreur lors de l'envoi du lien de paiement" });
    } finally {
      setPaymentLinkLoading(false);
    }
  };

  const copyPaymentLink = async () => {
    if (!paymentLinkUrl) return;
    try {
      await navigator.clipboard.writeText(paymentLinkUrl);
      setMsg({ type: "success", text: "Lien copié ✓" });
    } catch (_e) {
      setMsg({ type: "error", text: "Impossible de copier le lien" });
    }
  };

  const handleSendOnboardingLink = async () => {
    if (!tenantId || !onboardingEmail.trim()) {
      setMsg({ type: "error", text: "Email requis pour envoyer le lien onboarding" });
      return;
    }
    setOnboardingLoading(true);
    setMsg(null);
    try {
      const res = await sendTenantOnboardingLink(tenantId, {
        email: onboardingEmail.trim(),
        name: tenant?.name || "",
      });
      setMsg({ type: "success", text: `Lien envoyé à ${res?.email || onboardingEmail.trim()} ✓` });
      setShowOnboardingModal(false);
      onSaved?.();
    } catch (e) {
      setMsg({ type: "error", text: e?.message || "Erreur lors de l'envoi du lien onboarding" });
    } finally {
      setOnboardingLoading(false);
    }
  };

  const onboardingEligible = !((tenant?.params?.vapi_assistant_id || "").trim());

  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14, maxWidth: 900 }}>
      <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 16, padding: 22 }}>
        <div style={{ fontSize: 14, fontWeight: 700, color: C.text, marginBottom: 16 }}>Feature Flags</div>
        {FLAG_KEYS.map((key) => (
          <div key={key} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
            <span style={{ fontSize: 13, color: C.muted, fontFamily: "monospace" }}>{key}</span>
            <div
              role="button"
              tabIndex={0}
              onClick={() => setFlags((f) => ({ ...f, [key]: !f[key] }))}
              onKeyDown={(e) => e.key === "Enter" && setFlags((f) => ({ ...f, [key]: !f[key] }))}
              style={{
                width: 40,
                height: 22,
                borderRadius: 11,
                cursor: "pointer",
                background: flags[key] ? C.accent : C.border,
                position: "relative",
                transition: "background 0.2s",
              }}
            >
              <div
                style={{
                  width: 16,
                  height: 16,
                  borderRadius: "50%",
                  background: C.text,
                  position: "absolute",
                  top: 3,
                  left: flags[key] ? 21 : 3,
                  transition: "left 0.2s",
                }}
              />
            </div>
          </div>
        ))}
        <button
          type="button"
          onClick={saveFlags}
          disabled={saving}
          style={{
            marginTop: 8,
            width: "100%",
            padding: 10,
            borderRadius: 10,
            background: `linear-gradient(135deg,${C.accent},${C.accentDim})`,
            border: "none",
            color: C.bg,
            fontSize: 13,
            fontWeight: 700,
            cursor: "pointer",
            fontFamily: "inherit",
          }}
        >
          {saving ? "…" : "Sauvegarder les flags"}
        </button>
      </div>

      <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 16, padding: 22 }}>
        <div style={{ fontSize: 14, fontWeight: 700, color: C.text, marginBottom: 16 }}>Paramètres</div>
        {PARAM_KEYS.map((key) => (
          <div key={key} style={{ marginBottom: 12 }}>
            <div style={{ fontSize: 11, color: C.muted, marginBottom: 4, fontFamily: "monospace", textTransform: "uppercase", letterSpacing: 0.5 }}>{key}</div>
            <input
              value={params[key] || ""}
              onChange={(e) => setParams((p) => ({ ...p, [key]: e.target.value }))}
              style={{
                width: "100%",
                background: C.surface,
                border: `1px solid ${C.border}`,
                borderRadius: 8,
                padding: "8px 12px",
                color: C.text,
                fontSize: 13,
                fontFamily: "monospace",
                outline: "none",
              }}
            />
          </div>
        ))}

        {/* Section Agenda & Booking */}
        <div style={{ marginTop: 24, borderTop: `1px solid ${C.border}`, paddingTop: 16 }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: C.accent, marginBottom: 12 }}>📅 Agenda & Booking</div>

          <div style={{ marginBottom: 12 }}>
            <div style={{ fontSize: 11, color: C.muted, marginBottom: 4, display: "block" }}>Provider agenda</div>
            <select
              value={params.calendar_provider || "none"}
              onChange={(e) => setParams((p) => ({ ...p, calendar_provider: e.target.value }))}
              style={{
                width: "100%",
                background: C.surface,
                border: `1px solid ${C.border}`,
                borderRadius: 8,
                padding: "8px 12px",
                color: C.text,
                fontSize: 13,
                fontFamily: "inherit",
                outline: "none",
              }}
            >
              <option value="none">Aucun (SQLite fallback)</option>
              <option value="google">Google Calendar</option>
            </select>
          </div>

          <div style={{ marginBottom: 12 }}>
            <div style={{ fontSize: 11, color: C.muted, marginBottom: 4, display: "block" }}>Durée RDV (minutes)</div>
            <input
              type="number"
              min={5}
              max={120}
              step={5}
              value={params.booking_duration_minutes ?? 15}
              onChange={(e) => setParams((p) => ({ ...p, booking_duration_minutes: parseInt(e.target.value, 10) || 15 }))}
              style={{
                width: "100%",
                background: C.surface,
                border: `1px solid ${C.border}`,
                borderRadius: 8,
                padding: "8px 12px",
                color: C.text,
                fontSize: 13,
                fontFamily: "inherit",
                outline: "none",
              }}
            />
          </div>

          <div style={{ display: "flex", gap: 12, marginBottom: 12 }}>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 11, color: C.muted, marginBottom: 4, display: "block" }}>Heure début</div>
              <input
                type="number"
                min={6}
                max={12}
                value={params.booking_start_hour ?? 9}
                onChange={(e) => setParams((p) => ({ ...p, booking_start_hour: parseInt(e.target.value, 10) || 9 }))}
                style={{
                  width: "100%",
                  background: C.surface,
                  border: `1px solid ${C.border}`,
                  borderRadius: 8,
                  padding: "8px 12px",
                  color: C.text,
                  fontSize: 13,
                  fontFamily: "inherit",
                  outline: "none",
                }}
              />
            </div>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 11, color: C.muted, marginBottom: 4, display: "block" }}>Heure fin</div>
              <input
                type="number"
                min={14}
                max={22}
                value={params.booking_end_hour ?? 18}
                onChange={(e) => setParams((p) => ({ ...p, booking_end_hour: parseInt(e.target.value, 10) || 18 }))}
                style={{
                  width: "100%",
                  background: C.surface,
                  border: `1px solid ${C.border}`,
                  borderRadius: 8,
                  padding: "8px 12px",
                  color: C.text,
                  fontSize: 13,
                  fontFamily: "inherit",
                  outline: "none",
                }}
              />
            </div>
          </div>

          <div style={{ marginBottom: 12 }}>
            <div style={{ fontSize: 11, color: C.muted, marginBottom: 4, display: "block" }}>Buffer entre RDV (minutes)</div>
            <input
              type="number"
              min={0}
              max={30}
              step={5}
              value={params.booking_buffer_minutes ?? 0}
              onChange={(e) => setParams((p) => ({ ...p, booking_buffer_minutes: parseInt(e.target.value, 10) || 0 }))}
              style={{
                width: "100%",
                background: C.surface,
                border: `1px solid ${C.border}`,
                borderRadius: 8,
                padding: "8px 12px",
                color: C.text,
                fontSize: 13,
                fontFamily: "inherit",
                outline: "none",
              }}
            />
          </div>

          <div style={{ marginBottom: 12 }}>
            <div style={{ fontSize: 11, color: C.muted, marginBottom: 8, display: "block" }}>Jours de travail</div>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              {[
                ["L", 0],
                ["M", 1],
                ["Me", 2],
                ["J", 3],
                ["V", 4],
                ["S", 5],
                ["D", 6],
              ].map(([label, day]) => {
                const days = Array.isArray(params.booking_days) ? params.booking_days : [0, 1, 2, 3, 4];
                const active = days.includes(day);
                return (
                  <button
                    key={day}
                    type="button"
                    onClick={() => {
                      const next = active ? days.filter((d) => d !== day) : [...days, day].sort((a, b) => a - b);
                      setParams((p) => ({ ...p, booking_days: next }));
                    }}
                    style={{
                      width: 36,
                      height: 36,
                      borderRadius: 8,
                      fontSize: 12,
                      fontWeight: 500,
                      border: `1px solid ${active ? C.accent : C.border}`,
                      background: active ? C.accent : C.surface,
                      color: active ? C.bg : C.muted,
                      cursor: "pointer",
                      fontFamily: "inherit",
                      transition: "all 0.15s",
                    }}
                  >
                    {label}
                  </button>
                );
              })}
            </div>
          </div>

          <div
            style={{
              marginBottom: 12,
              padding: "10px 12px",
              borderRadius: 10,
              background: "rgba(0,229,160,0.08)",
              border: `1px solid rgba(0,229,160,0.18)`,
              fontSize: 12,
              color: C.text,
            }}
          >
            <div style={{ color: C.accent, fontWeight: 700, marginBottom: 4 }}>Aperçu live</div>
            <div>📅 {horairesPreview}</div>
            <div style={{ color: C.muted, marginTop: 4 }}>
              RDV de {bookingRules.booking_duration_minutes} min, buffer {bookingRules.booking_buffer_minutes} min
            </div>
          </div>

          <button
            type="button"
            onClick={saveHoraires}
            disabled={saving}
            style={{
              marginBottom: 12,
              width: "100%",
              padding: 10,
              borderRadius: 10,
              background: `linear-gradient(135deg,${C.accent},${C.accentDim})`,
              border: "none",
              color: C.bg,
              fontSize: 13,
              fontWeight: 700,
              cursor: "pointer",
              fontFamily: "inherit",
              opacity: saving ? 0.8 : 1,
            }}
          >
            {saving ? "…" : "Sauvegarder les horaires"}
          </button>
        </div>

        <button
          type="button"
          onClick={saveParams}
          disabled={saving}
          style={{
            marginTop: 4,
            width: "100%",
            padding: 10,
            borderRadius: 10,
            background: C.surface,
            border: `1px solid ${C.border}`,
            color: C.text,
            fontSize: 13,
            fontWeight: 700,
            cursor: "pointer",
            fontFamily: "inherit",
          }}
        >
          {saving ? "…" : "Sauvegarder les params"}
        </button>

        <div style={{ marginTop: 16, paddingTop: 16, borderTop: `1px solid ${C.border}` }}>
          {onboardingEligible && (
            <>
              <div style={{ fontSize: 13, fontWeight: 700, color: C.text, marginBottom: 8 }}>Onboarding client</div>
              <div style={{ fontSize: 12, color: C.muted, marginBottom: 10 }}>
                Envoie au client un lien vers le wizard pour qu&apos;il configure lui-même son assistant.
              </div>
              <button
                type="button"
                onClick={() => setShowOnboardingModal(true)}
                style={{
                  width: "100%",
                  padding: 10,
                  borderRadius: 10,
                  background: "rgba(91,168,255,0.12)",
                  border: `1px solid ${C.blue}55`,
                  color: C.blue,
                  fontSize: 13,
                  fontWeight: 700,
                  cursor: "pointer",
                  fontFamily: "inherit",
                  marginBottom: 16,
                }}
              >
                📧 Envoyer lien onboarding
              </button>
            </>
          )}
          <div style={{ fontSize: 13, fontWeight: 700, color: C.text, marginBottom: 8 }}>Paiement Stripe</div>
          <div style={{ fontSize: 12, color: C.muted, marginBottom: 10 }}>
            Envoie au client un lien Stripe pour ajouter sa carte pendant ou après les 30 jours d'essai.
          </div>
          <button
            type="button"
            onClick={handleSendPaymentLink}
            disabled={paymentLinkLoading}
            style={{
              width: "100%",
              padding: 10,
              borderRadius: 10,
              background: `linear-gradient(135deg,${C.accent},${C.accentDim})`,
              border: "none",
              color: C.bg,
              fontSize: 13,
              fontWeight: 700,
              cursor: "pointer",
              fontFamily: "inherit",
              opacity: paymentLinkLoading ? 0.7 : 1,
            }}
          >
            {paymentLinkLoading ? "Envoi..." : "Envoyer lien de paiement"}
          </button>
          {paymentLinkUrl && (
            <div style={{ marginTop: 10, display: "grid", gap: 8 }}>
              <input
                readOnly
                value={paymentLinkUrl}
                style={{
                  width: "100%",
                  background: C.surface,
                  border: `1px solid ${C.border}`,
                  borderRadius: 8,
                  padding: "8px 12px",
                  color: C.text,
                  fontSize: 12,
                  fontFamily: "monospace",
                  outline: "none",
                }}
              />
              <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
                <button
                  type="button"
                  onClick={copyPaymentLink}
                  style={{
                    padding: "8px 12px",
                    borderRadius: 8,
                    background: C.surface,
                    border: `1px solid ${C.border}`,
                    color: C.text,
                    fontSize: 12,
                    fontWeight: 700,
                    cursor: "pointer",
                    fontFamily: "inherit",
                  }}
                >
                  Copier le lien
                </button>
                <a href={paymentLinkUrl} target="_blank" rel="noopener noreferrer" style={{ color: C.blue, fontSize: 12 }}>
                  Ouvrir le lien
                </a>
                {paymentLinkEmail && <span style={{ fontSize: 12, color: C.muted }}>Envoyé à {paymentLinkEmail}</span>}
              </div>
            </div>
          )}
        </div>
      </div>

      {msg && (
        <div
          style={{
            gridColumn: "1/3",
            background: msg.type === "success" ? "rgba(0,229,160,0.08)" : "rgba(255,107,107,0.08)",
            border: `1px solid ${msg.type === "success" ? C.accent + "40" : C.danger + "40"}`,
            borderRadius: 10,
            padding: "12px 16px",
            fontSize: 13,
            color: msg.type === "success" ? C.accent : C.danger,
          }}
        >
          {msg.text}
        </div>
      )}
      {showOnboardingModal && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(3, 10, 18, 0.75)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 1000,
            padding: 20,
          }}
          onClick={(e) => {
            if (e.target === e.currentTarget) setShowOnboardingModal(false);
          }}
        >
          <div style={{ width: "100%", maxWidth: 460, background: C.surface, border: `1px solid ${C.border}`, borderRadius: 18, padding: 22 }}>
            <div style={{ fontSize: 16, fontWeight: 800, color: C.text, marginBottom: 8 }}>
              Envoyer lien onboarding
            </div>
            <div style={{ fontSize: 12, color: C.muted, marginBottom: 16 }}>
              Le client recevra un lien vers `/creer-assistante` pour finaliser lui-même la configuration.
            </div>
            <div style={{ fontSize: 11, color: C.muted, marginBottom: 6, textTransform: "uppercase", letterSpacing: 0.6 }}>
              Email du client
            </div>
            <input
              value={onboardingEmail}
              onChange={(e) => setOnboardingEmail(e.target.value)}
              placeholder="client@cabinet.fr"
              style={{
                width: "100%",
                background: C.card,
                border: `1px solid ${C.border}`,
                borderRadius: 10,
                padding: "10px 12px",
                color: C.text,
                fontSize: 13,
                fontFamily: "inherit",
                outline: "none",
              }}
            />
            <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 18 }}>
              <button
                type="button"
                onClick={() => setShowOnboardingModal(false)}
                style={{ padding: "9px 14px", borderRadius: 9, border: `1px solid ${C.border}`, background: "transparent", color: C.muted, cursor: "pointer", fontFamily: "inherit" }}
              >
                Annuler
              </button>
              <button
                type="button"
                onClick={handleSendOnboardingLink}
                disabled={onboardingLoading}
                style={{
                  padding: "9px 14px",
                  borderRadius: 9,
                  border: "none",
                  background: `linear-gradient(135deg,${C.accent},${C.accentDim})`,
                  color: C.bg,
                  cursor: "pointer",
                  fontWeight: 800,
                  fontFamily: "inherit",
                  opacity: onboardingLoading ? 0.7 : 1,
                }}
              >
                {onboardingLoading ? "Envoi..." : "Envoyer"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function TabFaq({ tenantId, tenant }) {
  return (
    <FaqEditor
      title={`FAQ du cabinet ${tenant?.name || ""}`.trim()}
      description="Cette FAQ est modifiable par l'admin et par le client. Chaque enregistrement met à jour la configuration locale puis tente de resynchroniser le prompt Vapi."
      loadFaq={() => getTenantFaq(tenantId)}
      saveFaq={(faq) => updateTenantFaq(tenantId, faq)}
      resetFaq={() => resetTenantFaq(tenantId)}
      variant="dark"
    />
  );
}

export default function AdminTenantPage() {
  const { id } = useParams();
  const tenantId = id;
  const navigate = useNavigate();
  const [tab, setTab] = useState("info");
  const [tenant, setTenant] = useState(null);
  const [dashboard, setDashboard] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    if (!tenantId) return;
    setLoading(true);
    setError(null);
    try {
      const [t, d] = await Promise.all([getTenant(tenantId), getTenantDashboard(tenantId)]);
      setTenant(t);
      setDashboard(d);
    } catch (e) {
      setError(e?.message || "Erreur chargement");
    } finally {
      setLoading(false);
    }
  }, [tenantId]);

  useEffect(() => {
    load();
  }, [load]);

  if (loading && !tenant) return <PageLoader />;
  if (error && !tenant) return <PageError msg={error} onRetry={load} />;

  return (
    <div style={{ minHeight: "100%", background: C.bg, fontFamily: "'DM Sans', system-ui, sans-serif" }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700;800&display=swap');
        * { box-sizing: border-box; }
        @keyframes uwi-fadein { from{opacity:0;transform:translateY(8px)} to{opacity:1;transform:translateY(0)} }
        @keyframes uwi-pulse { 0%,100%{opacity:1} 50%{opacity:.4} }
        ::-webkit-scrollbar{width:4px} ::-webkit-scrollbar-thumb{background:${C.border};border-radius:2px}
      `}</style>

      <div style={{ padding: "24px 32px", maxWidth: 1200, margin: "0 auto" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 16, marginBottom: 28 }}>
          <button
            type="button"
            onClick={() => navigate("/admin")}
            style={{
              background: C.surface,
              border: `1px solid ${C.border}`,
              borderRadius: 9,
              padding: "7px 14px",
              color: C.muted,
              fontSize: 13,
              fontWeight: 600,
              cursor: "pointer",
              fontFamily: "inherit",
            }}
          >
            ← Dashboard
          </button>

          <div style={{ flex: 1 }}>
            <h1 style={{ fontSize: 24, fontWeight: 800, color: C.text, letterSpacing: -0.8, marginBottom: 3 }}>
              {tenant?.name ?? `Tenant #${tenantId}`}
            </h1>
            <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
              <ServiceStatusBadge status={dashboard?.service_status?.status} />
              <span style={{ fontSize: 12, color: C.muted }}>ID #{tenantId}</span>
              {tenant?.timezone && <span style={{ fontSize: 12, color: C.muted }}>· {tenant.timezone}</span>}
            </div>
          </div>

          {dashboard?.counters_7d && (
            <div style={{ display: "flex", gap: 8 }}>
              {[
                ["📞", dashboard.counters_7d.calls_total, "appels"],
                ["✅", dashboard.counters_7d.bookings_confirmed, "RDV"],
                ["↗", dashboard.counters_7d.transfers, "transferts"],
                ["✕", dashboard.counters_7d.abandons, "abandons"],
              ].map(([ic, val, lbl]) => (
                <div key={lbl} style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 10, padding: "8px 12px", textAlign: "center", minWidth: 56 }}>
                  <div style={{ fontSize: 16, fontWeight: 800, color: C.text }}>{val ?? 0}</div>
                  <div style={{ fontSize: 9, color: C.muted, textTransform: "uppercase", letterSpacing: 0.5 }}>{lbl}</div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div style={{ display: "flex", gap: 4, marginBottom: 24, borderBottom: `1px solid ${C.border}`, paddingBottom: 0 }}>
          {TABS.map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => setTab(t.id)}
              style={{
                padding: "10px 16px",
                background: "transparent",
                border: "none",
                borderBottom: `2px solid ${tab === t.id ? C.accent : "transparent"}`,
                color: tab === t.id ? C.accent : C.muted,
                fontSize: 13,
                fontWeight: tab === t.id ? 700 : 500,
                cursor: "pointer",
                fontFamily: "inherit",
                display: "flex",
                alignItems: "center",
                gap: 6,
                transition: "all 0.15s",
                marginBottom: -1,
              }}
            >
              <span>{t.icon}</span>
              {t.label}
            </button>
          ))}
        </div>

        <div style={{ animation: "uwi-fadein 0.3s ease both" }} key={tab}>
          {tab === "info" && <TabInfo tenant={tenant} dashboard={dashboard} />}
          {tab === "timeline" && <TabTimeline tenantId={tenantId} />}
          {tab === "calls" && <TabCalls tenantId={tenantId} />}
          {tab === "invoices" && <TabInvoices tenantId={tenantId} />}
          {tab === "quota" && <TabQuota tenantId={tenantId} />}
          {tab === "faq" && <TabFaq tenantId={tenantId} tenant={tenant} />}
          {tab === "actions" && <TabActions tenantId={tenantId} tenant={tenant} onSaved={() => getTenant(tenantId).then(setTenant)} />}
        </div>
      </div>
    </div>
  );
}
