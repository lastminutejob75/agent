import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useAdminAuth } from "./AdminAuthProvider";
import { adminApi } from "../lib/adminApi.js";
import { T, font, keyframes, radius, shadow } from "./theme.js";

const API_BASE = (import.meta.env.VITE_UWI_API_BASE_URL || "").replace(/\/$/, "");
const SHOW_DIAGNOSTIC = import.meta.env.DEV;

// ── Sous-composants UI ──────────────────────────────────────────────────────

function ErrorBanner({ kind, children }) {
  const palette = {
    warning: { bg: T.yellowLight, border: `${T.yellow}80`, color: T.yellowText },
    error: { bg: T.redLight, border: `${T.red}40`, color: T.red },
  };
  const p = palette[kind] || palette.error;
  return (
    <div
      style={{
        marginBottom: 20,
        padding: "12px 14px",
        background: p.bg,
        border: `1px solid ${p.border}`,
        borderRadius: radius.lg,
        color: p.color,
        fontSize: 13,
        lineHeight: 1.5,
      }}
    >
      {children}
    </div>
  );
}

function FormField({ label, type, value, onChange, autoComplete, placeholder }) {
  return (
    <label style={{ display: "block", marginBottom: 16 }}>
      <span
        style={{
          display: "block",
          fontSize: 13,
          fontWeight: 500,
          color: T.text,
          marginBottom: 6,
        }}
      >
        {label}
      </span>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        required
        autoComplete={autoComplete}
        placeholder={placeholder}
        style={{
          display: "block",
          width: "100%",
          padding: "11px 14px",
          fontSize: 14,
          fontFamily: font.body,
          color: T.text,
          background: T.bgCard,
          border: `1px solid ${T.borderDark}`,
          borderRadius: radius.lg,
          outline: "none",
          transition: "border-color 0.15s, box-shadow 0.15s",
        }}
        onFocus={(e) => {
          e.currentTarget.style.borderColor = T.teal;
          e.currentTarget.style.boxShadow = `0 0 0 3px ${T.tealLight}`;
        }}
        onBlur={(e) => {
          e.currentTarget.style.borderColor = T.borderDark;
          e.currentTarget.style.boxShadow = "none";
        }}
      />
    </label>
  );
}

function PrimaryButton({ disabled, children, type = "button" }) {
  return (
    <button
      type={type}
      disabled={disabled}
      style={{
        width: "100%",
        padding: "12px 16px",
        background: T.teal,
        color: "#FFFFFF",
        border: "none",
        borderRadius: radius.lg,
        fontSize: 14,
        fontWeight: 600,
        fontFamily: font.body,
        cursor: disabled ? "not-allowed" : "pointer",
        opacity: disabled ? 0.5 : 1,
        transition: "background 0.15s",
      }}
      onMouseEnter={(e) => {
        if (!disabled) e.currentTarget.style.background = T.tealDark;
      }}
      onMouseLeave={(e) => {
        if (!disabled) e.currentTarget.style.background = T.teal;
      }}
    >
      {children}
    </button>
  );
}

function DiagnosticPanel() {
  const [open, setOpen] = useState(false);
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);

  useEffect(() => {
    if (!open) return;
    setErr(null);
    adminApi.authStatus().then(setData).catch((e) => setErr(e?.message || "Erreur"));
  }, [open]);

  return (
    <div style={{ marginTop: 20, paddingTop: 16, borderTop: `1px solid ${T.border}` }}>
      <button
        type="button"
        onClick={() => setOpen((s) => !s)}
        style={{
          fontSize: 11,
          color: T.textMuted,
          background: "transparent",
          border: "none",
          cursor: "pointer",
          padding: 0,
          fontFamily: font.body,
        }}
        onMouseEnter={(e) => (e.currentTarget.style.color = T.textSecondary)}
        onMouseLeave={(e) => (e.currentTarget.style.color = T.textMuted)}
      >
        {open ? "▼" : "▶"} Diagnostic backend
      </button>
      {open && (
        <div
          style={{
            marginTop: 10,
            padding: 12,
            background: T.bgSubtle,
            border: `1px solid ${T.border}`,
            borderRadius: radius.md,
            fontSize: 11,
            fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
            color: T.textSecondary,
            lineHeight: 1.7,
          }}
        >
          <div>API : {API_BASE || "(non configuré)"}</div>
          {err && <div style={{ color: T.red, marginTop: 4 }}>{err}</div>}
          {data && (
            <div style={{ marginTop: 6 }}>
              <div>email_set: {String(data.email_set)}</div>
              <div>password_plain_set: {String(data.password_plain_set)}</div>
              <div>password_hash_set: {String(data.password_hash_set)}</div>
              <div>admin_token_set: {String(data.admin_token_set)}</div>
              <div>jwt_secret_set: {String(data.jwt_secret_set)}</div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Page ────────────────────────────────────────────────────────────────────

export default function AdminLogin() {
  const { login, isAuthed, sessionPersistError } = useAdminAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const from = location.state?.from?.pathname || "/admin";

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState(null);

  useEffect(() => {
    if (isAuthed) navigate(from, { replace: true });
  }, [isAuthed, from, navigate]);

  if (isAuthed) {
    return (
      <div
        style={{
          minHeight: "100vh",
          background: T.bgPage,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontFamily: font.body,
        }}
      >
        <style>{keyframes}</style>
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            gap: 12,
            color: T.textMuted,
            fontSize: 14,
          }}
        >
          <div
            style={{
              width: 32,
              height: 32,
              border: `2px solid ${T.teal}`,
              borderTopColor: "transparent",
              borderRadius: "50%",
              animation: "spin 0.8s linear infinite",
            }}
          />
          <span>Redirection…</span>
          <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
        </div>
      </div>
    );
  }

  async function onSubmit(e) {
    e.preventDefault();
    setErr(null);
    setLoading(true);
    try {
      const result = await login(email, password);
      if (result?.sessionPersistError) return;
      navigate(from, { replace: true });
    } catch {
      setErr("Identifiants invalides.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div
      style={{
        minHeight: "100vh",
        background: T.bgPage,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 16,
        fontFamily: font.body,
        color: T.text,
      }}
    >
      <style>{keyframes}</style>
      <div style={{ width: "100%", maxWidth: 420 }}>
        {/* En-tete */}
        <div style={{ textAlign: "center", marginBottom: 32 }}>
          <div
            style={{
              display: "inline-flex",
              width: 56,
              height: 56,
              borderRadius: radius.xl,
              background: `linear-gradient(135deg, ${T.teal}, ${T.tealDark})`,
              color: "#FFFFFF",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 24,
              fontWeight: 800,
              fontFamily: font.display,
              letterSpacing: -0.5,
              boxShadow: `0 8px 24px ${T.teal}40`,
            }}
          >
            U
          </div>
          <h1
            style={{
              margin: "16px 0 4px",
              fontSize: 24,
              fontWeight: 700,
              fontFamily: font.display,
              color: T.text,
              letterSpacing: -0.5,
            }}
          >
            UWi Admin
          </h1>
          <p style={{ margin: 0, fontSize: 13, color: T.textMuted }}>
            Connexion sécurisée
          </p>
        </div>

        {/* Carte principale */}
        <div
          style={{
            background: T.bgCard,
            border: `1px solid ${T.border}`,
            borderRadius: radius.xxl,
            padding: 32,
            boxShadow: shadow.card,
          }}
        >
          {sessionPersistError ? (
            <ErrorBanner kind="warning">
              Session non persistée. Vérifiez SameSite=None + Secure (voir
              docs/ADMIN_LOGIN_COOKIE.md).
            </ErrorBanner>
          ) : err ? (
            <ErrorBanner kind="error">{err}</ErrorBanner>
          ) : null}

          <form onSubmit={onSubmit}>
            <FormField
              label="Email"
              type="email"
              value={email}
              onChange={setEmail}
              autoComplete="email"
              placeholder="admin@cabinet.fr"
            />
            <FormField
              label="Mot de passe"
              type="password"
              value={password}
              onChange={setPassword}
              autoComplete="current-password"
              placeholder="••••••••"
            />
            <PrimaryButton type="submit" disabled={loading}>
              {loading ? "Connexion…" : "Se connecter"}
            </PrimaryButton>
          </form>

        </div>

        <p
          style={{
            margin: "20px 0 0",
            textAlign: "center",
            fontSize: 11,
            color: T.textMuted,
          }}
        >
          Accès réservé aux administrateurs.
        </p>

        {SHOW_DIAGNOSTIC && <DiagnosticPanel />}
      </div>
    </div>
  );
}
