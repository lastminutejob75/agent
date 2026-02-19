import { useEffect, useState } from "react";
import { useSearchParams, Navigate } from "react-router-dom";
import { api, setTenantToken } from "../lib/api";

const IMPERSONATION_KEY = "uwi_impersonation";

export function setImpersonation(tenantName) {
  try {
    if (tenantName) {
      localStorage.setItem(IMPERSONATION_KEY, JSON.stringify({ tenant_name: tenantName }));
    } else {
      localStorage.removeItem(IMPERSONATION_KEY);
    }
  } catch (_) {}
}

export function getImpersonation() {
  try {
    const raw = localStorage.getItem(IMPERSONATION_KEY);
    if (!raw) return null;
    return JSON.parse(raw);
  } catch (_) {
    return null;
  }
}

export default function ImpersonatePage() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token");
  const [err, setErr] = useState(null);
  const [loading, setLoading] = useState(!!token);

  useEffect(() => {
    if (!token) return;
    setErr(null);
    api
      .tenantImpersonateValidate(token)
      .then((r) => {
        setTenantToken(token);
        setImpersonation(r.tenant_name || "Client");
        window.location.replace("/app");
      })
      .catch((e) => {
        setErr(e?.message || e?.data?.detail || "Token invalide ou expiré");
        setLoading(false);
      });
  }, [token]);

  if (!token) {
    return <Navigate to="/login" replace />;
  }
  if (loading && !err) {
    return (
      <div className="mx-auto max-w-md p-8 text-center text-gray-600">
        <div className="inline-block h-8 w-8 animate-spin rounded-full border-2 border-indigo-500 border-t-transparent mb-4" />
        <p>Ouverture du dashboard client…</p>
      </div>
    );
  }
  return (
    <div className="mx-auto max-w-md p-8">
      <div className="rounded-xl border border-red-200 bg-red-50 p-6">
        <h1 className="text-lg font-bold text-red-900">Impersonation impossible</h1>
        <p className="mt-2 text-sm text-red-800">{err}</p>
        <a href="/login" className="mt-4 inline-block text-red-700 underline">
          Retour à la connexion
        </a>
      </div>
    </div>
  );
}
