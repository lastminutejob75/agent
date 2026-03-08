import { useCallback, useEffect, useMemo, useState } from "react";

const THEMES = {
  light: {
    bg: "#f8fafc",
    card: "#ffffff",
    border: "#e2e8f0",
    text: "#0d1b2e",
    muted: "#64748b",
    accent: "#00d4a0",
    accentDim: "#00b389",
    danger: "#dc2626",
    dangerBg: "rgba(220,38,38,0.08)",
    successBg: "rgba(0,212,160,0.08)",
    surface: "#f8fafc",
    surfaceAlt: "#f1f5f9",
  },
  dark: {
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
  },
};

function createFaqId() {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `faq_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}

function normalizeFaq(rawFaq) {
  if (!Array.isArray(rawFaq)) return [];
  return rawFaq
    .map((category, categoryIndex) => {
      const name = String(category?.category || "").trim() || `Catégorie ${categoryIndex + 1}`;
      const items = Array.isArray(category?.items)
        ? category.items
            .map((item, itemIndex) => ({
              id: String(item?.id || `faq_${categoryIndex + 1}_${itemIndex + 1}`),
              question: String(item?.question || ""),
              answer: String(item?.answer || ""),
              active: item?.active !== false,
            }))
            .filter((item) => item.question.trim() || item.answer.trim())
        : [];
      return { category: name, items };
    })
    .filter((category) => category.category.trim());
}

function countActiveItems(faq) {
  return faq.reduce(
    (total, category) => total + category.items.filter((item) => item.active !== false).length,
    0,
  );
}

export default function FaqEditor({
  title = "FAQ",
  description = "",
  loadFaq,
  saveFaq,
  resetFaq,
  variant = "light",
}) {
  const theme = THEMES[variant] || THEMES.light;
  const [faq, setFaq] = useState([]);
  const [expanded, setExpanded] = useState({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [resetting, setResetting] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const hydrate = useCallback((data) => {
    const normalized = normalizeFaq(data);
    setFaq(normalized);
    setExpanded((current) => {
      const next = {};
      normalized.forEach((category, index) => {
        const key = category.category || `cat_${index}`;
        next[key] = current[key] ?? true;
      });
      return next;
    });
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    setSuccess("");
    try {
      const data = await loadFaq();
      hydrate(data);
    } catch (e) {
      setError(e?.message || "Impossible de charger la FAQ.");
    } finally {
      setLoading(false);
    }
  }, [hydrate, loadFaq]);

  useEffect(() => {
    load();
  }, [load]);

  const summary = useMemo(() => {
    const categories = faq.length;
    const questions = faq.reduce((total, category) => total + category.items.length, 0);
    const activeItems = countActiveItems(faq);
    return { categories, questions, activeItems };
  }, [faq]);

  const updateCategory = (categoryIndex, patch) => {
    setFaq((current) =>
      current.map((category, index) =>
        index === categoryIndex ? { ...category, ...patch } : category,
      ),
    );
  };

  const removeCategory = (categoryIndex) => {
    setFaq((current) => current.filter((_, index) => index !== categoryIndex));
  };

  const addCategory = () => {
    const name = `Nouvelle catégorie ${faq.length + 1}`;
    setFaq((current) => [...current, { category: name, items: [] }]);
    setExpanded((current) => ({ ...current, [name]: true }));
  };

  const addQuestion = (categoryIndex) => {
    setFaq((current) =>
      current.map((category, index) =>
        index === categoryIndex
          ? {
              ...category,
              items: [
                ...category.items,
                {
                  id: createFaqId(),
                  question: "",
                  answer: "",
                  active: true,
                },
              ],
            }
          : category,
      ),
    );
  };

  const updateQuestion = (categoryIndex, itemIndex, patch) => {
    setFaq((current) =>
      current.map((category, index) =>
        index === categoryIndex
          ? {
              ...category,
              items: category.items.map((item, idx) =>
                idx === itemIndex ? { ...item, ...patch } : item,
              ),
            }
          : category,
      ),
    );
  };

  const removeQuestion = (categoryIndex, itemIndex) => {
    setFaq((current) =>
      current.map((category, index) =>
        index === categoryIndex
          ? {
              ...category,
              items: category.items.filter((_, idx) => idx !== itemIndex),
            }
          : category,
      ),
    );
  };

  const toggleExpanded = (key) => {
    setExpanded((current) => ({ ...current, [key]: !current[key] }));
  };

  const handleSave = async () => {
    setSaving(true);
    setError("");
    setSuccess("");
    try {
      const payload = normalizeFaq(faq);
      const response = await saveFaq(payload);
      hydrate(response?.faq || payload);
      setSuccess("FAQ enregistrée et synchronisée.");
    } catch (e) {
      setError(e?.message || "Impossible d'enregistrer la FAQ.");
    } finally {
      setSaving(false);
    }
  };

  const handleReset = async () => {
    setResetting(true);
    setError("");
    setSuccess("");
    try {
      const response = await resetFaq();
      hydrate(response?.faq || []);
      setSuccess("FAQ réinitialisée avec les valeurs par défaut.");
    } catch (e) {
      setError(e?.message || "Impossible de réinitialiser la FAQ.");
    } finally {
      setResetting(false);
    }
  };

  if (loading) {
    return (
      <div style={{ padding: 20, borderRadius: 16, border: `1px solid ${theme.border}`, background: theme.card, color: theme.muted }}>
        Chargement de la FAQ…
      </div>
    );
  }

  return (
    <div
      style={{
        borderRadius: 18,
        border: `1px solid ${theme.border}`,
        background: theme.card,
        color: theme.text,
        padding: 20,
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", gap: 16, alignItems: "flex-start", marginBottom: 18, flexWrap: "wrap" }}>
        <div>
          <div style={{ fontSize: 22, fontWeight: 800, marginBottom: 6 }}>{title}</div>
          {description ? (
            <div style={{ fontSize: 14, color: theme.muted, maxWidth: 760 }}>{description}</div>
          ) : null}
        </div>
        <div
          style={{
            display: "flex",
            gap: 10,
            flexWrap: "wrap",
            padding: "10px 12px",
            borderRadius: 12,
            background: theme.surface,
            border: `1px solid ${theme.border}`,
            fontSize: 12,
            color: theme.muted,
          }}
        >
          <span>{summary.categories} catégories</span>
          <span>{summary.questions} questions</span>
          <span>{summary.activeItems} actives</span>
        </div>
      </div>

      <div style={{ display: "grid", gap: 14 }}>
        {faq.map((category, categoryIndex) => {
          const categoryKey = category.category || `category_${categoryIndex}`;
          const isOpen = expanded[categoryKey] ?? true;
          return (
            <div
              key={`${categoryKey}_${categoryIndex}`}
              style={{
                borderRadius: 14,
                border: `1px solid ${theme.border}`,
                background: theme.surface,
                overflow: "hidden",
              }}
            >
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  gap: 10,
                  padding: 14,
                  borderBottom: isOpen ? `1px solid ${theme.border}` : "none",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 10, flex: 1, minWidth: 0 }}>
                  <button
                    type="button"
                    onClick={() => toggleExpanded(categoryKey)}
                    style={{
                      width: 28,
                      height: 28,
                      borderRadius: 8,
                      border: `1px solid ${theme.border}`,
                      background: theme.surfaceAlt,
                      color: theme.text,
                      cursor: "pointer",
                      fontWeight: 700,
                    }}
                  >
                    {isOpen ? "−" : "+"}
                  </button>
                  <input
                    value={category.category}
                    onChange={(event) => updateCategory(categoryIndex, { category: event.target.value })}
                    placeholder="Nom de catégorie"
                    style={{
                      flex: 1,
                      minWidth: 0,
                      border: `1px solid ${theme.border}`,
                      background: theme.card,
                      color: theme.text,
                      borderRadius: 10,
                      padding: "10px 12px",
                      fontSize: 14,
                      fontWeight: 700,
                    }}
                  />
                </div>
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                  <button
                    type="button"
                    onClick={() => addQuestion(categoryIndex)}
                    style={{
                      padding: "9px 12px",
                      borderRadius: 10,
                      border: `1px solid ${theme.border}`,
                      background: theme.surfaceAlt,
                      color: theme.text,
                      cursor: "pointer",
                      fontWeight: 700,
                    }}
                  >
                    + Ajouter une question
                  </button>
                  <button
                    type="button"
                    onClick={() => removeCategory(categoryIndex)}
                    style={{
                      padding: "9px 12px",
                      borderRadius: 10,
                      border: `1px solid ${theme.danger}40`,
                      background: theme.dangerBg,
                      color: theme.danger,
                      cursor: "pointer",
                      fontWeight: 700,
                    }}
                  >
                    Supprimer
                  </button>
                </div>
              </div>

              {isOpen ? (
                <div style={{ display: "grid", gap: 12, padding: 14 }}>
                  {category.items.length === 0 ? (
                    <div
                      style={{
                        borderRadius: 12,
                        border: `1px dashed ${theme.border}`,
                        padding: 14,
                        color: theme.muted,
                        fontSize: 13,
                      }}
                    >
                      Cette catégorie est vide. Ajoutez une ou plusieurs questions.
                    </div>
                  ) : null}
                  {category.items.map((item, itemIndex) => (
                    <div
                      key={item.id}
                      style={{
                        borderRadius: 12,
                        border: `1px solid ${theme.border}`,
                        background: theme.card,
                        padding: 14,
                      }}
                    >
                      <div style={{ display: "flex", justifyContent: "space-between", gap: 10, marginBottom: 12, alignItems: "center", flexWrap: "wrap" }}>
                        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                          <button
                            type="button"
                            onClick={() => updateQuestion(categoryIndex, itemIndex, { active: !item.active })}
                            style={{
                              padding: "6px 10px",
                              borderRadius: 999,
                              border: `1px solid ${item.active ? theme.accent : theme.border}`,
                              background: item.active ? theme.successBg : theme.surfaceAlt,
                              color: item.active ? theme.accentDim : theme.muted,
                              cursor: "pointer",
                              fontSize: 12,
                              fontWeight: 700,
                            }}
                          >
                            {item.active ? "Active" : "Inactive"}
                          </button>
                          <span style={{ fontSize: 12, color: theme.muted, fontFamily: "monospace" }}>{item.id}</span>
                        </div>
                        <button
                          type="button"
                          onClick={() => removeQuestion(categoryIndex, itemIndex)}
                          style={{
                            padding: "6px 10px",
                            borderRadius: 8,
                            border: `1px solid ${theme.danger}40`,
                            background: theme.dangerBg,
                            color: theme.danger,
                            cursor: "pointer",
                            fontWeight: 700,
                          }}
                        >
                          Retirer
                        </button>
                      </div>

                      <div style={{ display: "grid", gap: 10 }}>
                        <label style={{ display: "grid", gap: 6 }}>
                          <span style={{ fontSize: 12, color: theme.muted }}>Question</span>
                          <input
                            value={item.question}
                            onChange={(event) => updateQuestion(categoryIndex, itemIndex, { question: event.target.value })}
                            placeholder="Ex. Êtes-vous ouvert le samedi ?"
                            style={{
                              width: "100%",
                              border: `1px solid ${theme.border}`,
                              background: theme.surface,
                              color: theme.text,
                              borderRadius: 10,
                              padding: "10px 12px",
                              fontSize: 14,
                            }}
                          />
                        </label>
                        <label style={{ display: "grid", gap: 6 }}>
                          <span style={{ fontSize: 12, color: theme.muted }}>Réponse</span>
                          <textarea
                            value={item.answer}
                            onChange={(event) => updateQuestion(categoryIndex, itemIndex, { answer: event.target.value })}
                            placeholder="Ex. Non, nous sommes ouverts du lundi au vendredi."
                            rows={4}
                            style={{
                              width: "100%",
                              resize: "vertical",
                              border: `1px solid ${theme.border}`,
                              background: theme.surface,
                              color: theme.text,
                              borderRadius: 10,
                              padding: "10px 12px",
                              fontSize: 14,
                              fontFamily: "inherit",
                            }}
                          />
                        </label>
                      </div>
                    </div>
                  ))}
                </div>
              ) : null}
            </div>
          );
        })}

        <button
          type="button"
          onClick={addCategory}
          style={{
            padding: "12px 14px",
            borderRadius: 12,
            border: `1px dashed ${theme.border}`,
            background: theme.surfaceAlt,
            color: theme.text,
            cursor: "pointer",
            fontWeight: 700,
          }}
        >
          + Nouvelle catégorie
        </button>
      </div>

      {error ? (
        <div
          style={{
            marginTop: 16,
            padding: "12px 14px",
            borderRadius: 12,
            background: theme.dangerBg,
            border: `1px solid ${theme.danger}40`,
            color: theme.danger,
            fontSize: 13,
          }}
        >
          {error}
        </div>
      ) : null}

      {success ? (
        <div
          style={{
            marginTop: 16,
            padding: "12px 14px",
            borderRadius: 12,
            background: theme.successBg,
            border: `1px solid ${theme.accent}40`,
            color: theme.accentDim,
            fontSize: 13,
            fontWeight: 700,
          }}
        >
          {success}
        </div>
      ) : null}

      <div style={{ display: "flex", gap: 10, justifyContent: "flex-end", marginTop: 20, flexWrap: "wrap" }}>
        <button
          type="button"
          onClick={handleReset}
          disabled={resetting}
          style={{
            padding: "11px 14px",
            borderRadius: 12,
            border: `1px solid ${theme.border}`,
            background: theme.surfaceAlt,
            color: theme.text,
            cursor: "pointer",
            fontWeight: 700,
            opacity: resetting ? 0.7 : 1,
          }}
        >
          {resetting ? "Réinitialisation…" : "Réinitialiser"}
        </button>
        <button
          type="button"
          onClick={handleSave}
          disabled={saving}
          style={{
            padding: "11px 16px",
            borderRadius: 12,
            border: "none",
            background: `linear-gradient(135deg, ${theme.accent}, ${theme.accentDim})`,
            color: variant === "dark" ? "#04131f" : "#0d1b2e",
            cursor: "pointer",
            fontWeight: 800,
            opacity: saving ? 0.7 : 1,
          }}
        >
          {saving ? "Enregistrement…" : "Enregistrer"}
        </button>
      </div>
    </div>
  );
}
