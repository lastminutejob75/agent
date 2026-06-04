import { useState } from "react";
import { Download } from "lucide-react";
import { Button } from "./Button.jsx";
import { getApiUrl } from "../../../lib/authConfig.js";

/**
 * Bouton d'export CSV.
 * Telecharge directement un fichier en utilisant `fetch + Blob` avec credentials.
 *
 * Props :
 * - url : URL backend (relative, sera prefixee par VITE_UWI_API_BASE_URL).
 * - filename : nom propose au telechargement.
 * - label : texte du bouton (defaut "Exporter CSV").
 * - bearerToken : optionnel, sinon credentials: include (cookie).
 * - onError : callback en cas d'echec.
 * - size : "md" / "sm" — passe a Button.
 */
export default function ExportCsvButton({
  url,
  filename = "export.csv",
  label = "Exporter CSV",
  bearerToken = null,
  onError,
  size = "md",
  variant = "ghost",
}) {
  const [loading, setLoading] = useState(false);

  const handleClick = async () => {
    setLoading(true);
    try {
      const base = getApiUrl();
      const headers = {};
      if (bearerToken) headers["Authorization"] = `Bearer ${bearerToken}`;

      const res = await fetch(base + url, {
        credentials: "include",
        headers,
      });
      if (!res.ok) {
        let detail = `Erreur ${res.status}`;
        try {
          const data = await res.json();
          if (data?.detail) detail = String(data.detail);
        } catch {
          /* body non-JSON, on garde le code HTTP */
        }
        throw new Error(detail);
      }

      // Suggested filename via Content-Disposition (priorite serveur > prop)
      const cd = res.headers.get("content-disposition") || "";
      const match = cd.match(/filename="?([^"]+)"?/i);
      const finalName = match?.[1] || filename;

      const blob = await res.blob();
      const blobUrl = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = blobUrl;
      a.download = finalName;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(blobUrl);
    } catch (e) {
      console.error("Export CSV failed:", e);
      if (typeof onError === "function") onError(e);
      else alert(`Export impossible : ${e?.message || e}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Button
      variant={variant}
      size={size}
      iconLeft={<Download size={14} strokeWidth={2.4} />}
      onClick={handleClick}
      disabled={loading}
      title="Telecharger en CSV (compatible Excel)"
    >
      {loading ? "Export..." : label}
    </Button>
  );
}
