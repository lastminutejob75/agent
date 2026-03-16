import { useCallback, useEffect, useState } from "react";
import { api } from "../lib/api.js";

const THEME = {
  bg: "#0f2236",
  card: "#132840",
  border: "#1e3d56",
  text: "#ffffff",
  muted: "#6b90a8",
  accent: "#00e5a0",
  accentDim: "#00b87c",
  danger: "#ff6b6b",
  dangerBg: "rgba(255,107,107,0.08)",
  successBg: "rgba(0,229,160,0.08)",
  surface: "#0f2236",
  surfaceAlt: "#10263d",
};

const FIELDS = [
  {
    key: "address_line1",
    label: "Adresse du cabinet",
    placeholder: "Ex. 12 rue de la Santé",
    type: "text",
    group: "Informations pratiques",
  },
  {
    key: "postal_code",
    label: "Code postal",
    placeholder: "Ex. 75013",
    type: "text",
    group: "Informations pratiques",
  },
  {
    key: "city",
    label: "Ville",
    placeholder: "Ex. Paris",
    type: "text",
    group: "Informations pratiques",
  },
  {
    key: "parking_access",
    label: "Parking et accès",
    placeholder: "Ex. Parking public à 50m, accès métro ligne 6",
    type: "textarea",
    group: "Informations pratiques",
  },
  {
    key: "pmr_accessibility",
    label: "Accessibilité PMR",
    placeholder: "Ex. Oui, le cabinet est de plain-pied et accessible aux fauteuils roulants.",
    type: "textarea",
    group: "Informations pratiques",
  },
  {
    key: "payment_methods",
    label: "Moyens de paiement acceptés",
    placeholder: "Ex. carte bancaire, espèces, chèques",
    type: "text",
    group: "Paiement",
  },
  {
    key: "third_party_payment",
    label: "Politique tiers payant",
    placeholder: "Ex. Le tiers payant est pratiqué avec la plupart des mutuelles.",
    type: "textarea",
    group: "Paiement",
  },
  {
    key: "new_patients_policy",
    label: "Politique nouveaux patients",
    placeholder: "Ex. Oui, le cabinet accepte les nouveaux patients.",
    type: "textarea",
    group: "Patients",
  },
  {
    key: "results_policy",
    label: "Récupération des résultats",
    placeholder: "Ex. Les résultats sont disponibles au cabinet ou envoyés par courrier sécurisé.",
    type: "textarea",
    group: "Suivi",
  },
];

function groupFields(fields) {
  const groups = {};
  for (const f of fields) {
    if (!groups[f.group]) groups[f.group] = [];
    groups[f.group].push(f);
  }
  return groups;
}

export default function AppFaq() {
  const [values, setValues] = useState({});
  const [horaires, setHoraires] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const me = await api.tenantMe();
      const params = me?.params || me || {};
      const initial = {};
      for (const f of FIELDS) {
        initial[f.key] = String(params[f.key] || "");
      }
      setValues(initial);

      const days = params.booking_days || [0, 1, 2, 3, 4];
      const dayNames = { 0: "Lun", 1: "Mar", 2: "Mer", 3: "Jeu", 4: "Ven", 5: "Sam", 6: "Dim" };
      const dayList = (Array.isArray(days) ? days : [0, 1, 2, 3, 4])
        .map((d) => dayNames[d])
        .filter(Boolean);
      const start = params.booking_start_hour || 9;
      const end = params.booking_end_hour || 18;
      setHoraires(`${dayList.join(", ")} · ${start}h–${end}h`);
    } catch (e) {
      setError(e?.message || "Impossible de charger la configuration.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const handleChange = (key, value) => {
    setValues((prev) => ({ ...prev, [key]: value }));
  };

  const handleSave = async () => {
    setSaving(true);
    setError("");
    setSuccess("");
    try {
      const params = {};
      for (const f of FIELDS) {
        const val = (values[f.key] || "").trim();
        if (val) params[f.key] = val;
      }
      await api.tenantPatchParams(params);
      await api.tenantUpdateFaq([]);
      setSuccess("Configuration enregistrée et FAQ synchronisée avec votre assistante.");
    } catch (e) {
      setError(e?.message || "Impossible d'enregistrer.");
    } finally {
      setSaving(false);
    }
  };

  const groups = groupFields(FIELDS);

  if (loading) {
    return (
      <div className="page">
        <div
          className="dcard"
          style={{ maxWidth: 980, padding: 20, color: THEME.muted, background: THEME.card, borderRadius: 16, border: `1px solid ${THEME.border}` }}
        >
          Chargement de la configuration FAQ...
        </div>
      </div>
    );
  }

  return (
    <div className="page">
      <div className="dcard" style={{ maxWidth: 980 }}>
        <div
          style={{
            borderRadius: 18,
            border: `1px solid ${THEME.border}`,
            background: THEME.card,
            color: THEME.text,
            padding: 24,
          }}
        >
          <div style={{ marginBottom: 20 }}>
            <div style={{ fontSize: 22, fontWeight: 800, marginBottom: 6 }}>
              Configuration FAQ du cabinet
            </div>
            <div style={{ fontSize: 14, color: THEME.muted, maxWidth: 760 }}>
              Renseignez les informations de votre cabinet. Votre assistante vocale utilisera ces
              informations pour répondre aux patients. Les champs laissés vides utiliseront une
              réponse par défaut.
            </div>
          </div>

          {horaires && (
            <div
              style={{
                padding: "12px 16px",
                borderRadius: 12,
                background: THEME.surfaceAlt,
                border: `1px solid ${THEME.border}`,
                marginBottom: 20,
                display: "flex",
                alignItems: "center",
                gap: 12,
              }}
            >
              <span style={{ fontSize: 13, color: THEME.muted }}>Horaires actuels :</span>
              <span style={{ fontSize: 14, fontWeight: 700 }}>{horaires}</span>
              <span style={{ fontSize: 12, color: THEME.muted, marginLeft: "auto" }}>
                Modifiable dans Agenda &gt; Horaires
              </span>
            </div>
          )}

          <div style={{ display: "grid", gap: 20 }}>
            {Object.entries(groups).map(([groupName, fields]) => (
              <div
                key={groupName}
                style={{
                  borderRadius: 14,
                  border: `1px solid ${THEME.border}`,
                  background: THEME.surface,
                  overflow: "hidden",
                }}
              >
                <div
                  style={{
                    padding: "12px 16px",
                    borderBottom: `1px solid ${THEME.border}`,
                    fontWeight: 700,
                    fontSize: 15,
                  }}
                >
                  {groupName}
                </div>
                <div style={{ padding: 16, display: "grid", gap: 14 }}>
                  {fields.map((field) => (
                    <label key={field.key} style={{ display: "grid", gap: 6 }}>
                      <span style={{ fontSize: 13, color: THEME.muted, fontWeight: 600 }}>
                        {field.label}
                      </span>
                      {field.type === "textarea" ? (
                        <textarea
                          value={values[field.key] || ""}
                          onChange={(e) => handleChange(field.key, e.target.value)}
                          placeholder={field.placeholder}
                          rows={3}
                          style={{
                            width: "100%",
                            resize: "vertical",
                            border: `1px solid ${THEME.border}`,
                            background: THEME.card,
                            color: THEME.text,
                            borderRadius: 10,
                            padding: "10px 12px",
                            fontSize: 14,
                            fontFamily: "inherit",
                          }}
                        />
                      ) : (
                        <input
                          type="text"
                          value={values[field.key] || ""}
                          onChange={(e) => handleChange(field.key, e.target.value)}
                          placeholder={field.placeholder}
                          style={{
                            width: "100%",
                            border: `1px solid ${THEME.border}`,
                            background: THEME.card,
                            color: THEME.text,
                            borderRadius: 10,
                            padding: "10px 12px",
                            fontSize: 14,
                          }}
                        />
                      )}
                    </label>
                  ))}
                </div>
              </div>
            ))}
          </div>

          {error && (
            <div
              style={{
                marginTop: 16,
                padding: "12px 14px",
                borderRadius: 12,
                background: THEME.dangerBg,
                border: `1px solid ${THEME.danger}40`,
                color: THEME.danger,
                fontSize: 13,
              }}
            >
              {error}
            </div>
          )}

          {success && (
            <div
              style={{
                marginTop: 16,
                padding: "12px 14px",
                borderRadius: 12,
                background: THEME.successBg,
                border: `1px solid ${THEME.accent}40`,
                color: THEME.accentDim,
                fontSize: 13,
                fontWeight: 700,
              }}
            >
              {success}
            </div>
          )}

          <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 20 }}>
            <button
              type="button"
              onClick={handleSave}
              disabled={saving}
              style={{
                padding: "12px 20px",
                borderRadius: 12,
                border: "none",
                background: `linear-gradient(135deg, ${THEME.accent}, ${THEME.accentDim})`,
                color: "#04131f",
                cursor: "pointer",
                fontWeight: 800,
                fontSize: 14,
                opacity: saving ? 0.7 : 1,
              }}
            >
              {saving ? "Enregistrement..." : "Enregistrer et synchroniser"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
