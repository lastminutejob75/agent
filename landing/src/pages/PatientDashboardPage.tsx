import React, { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../lib/api.js";

type Patient = {
  id: string;
  initials: string;
  name: string;
  phone: string;
  date: string;
  color: string;
};

type ModalType = "profile" | "addNote" | "addDocument" | "history" | null;
type ViewType = "overview" | "appointments" | "history";
type RequestContext = {
  id: string;
  phone: string;
  patientName: string;
  summary: string;
  type: string;
  status: string;
  source: string;
  createdAtLabel: string;
};

type PatientNote = {
  id: number;
  text: string;
  author: string;
  created_at: string;
};

type PatientDocument = {
  id: number;
  original_name: string;
  mime_type: string;
  size_bytes: number;
  created_at: string;
};

const patients: Patient[] = [
  { id: "p1", initials: "JD", name: "Jean Durand", phone: "06 90 00 01 58", date: "Aujourd'hui", color: "from-[#008EA1] to-[#004866]" },
  { id: "p2", initials: "SL", name: "Sophie Leroy", phone: "06 12 34 56 78", date: "Hier", color: "from-[#00A686] to-[#007C73]" },
  { id: "p3", initials: "PB", name: "Paul Bernard", phone: "06 23 45 67 89", date: "19/05/2026", color: "from-[#7256F4] to-[#5338C9]" },
  { id: "p4", initials: "CM", name: "Claire Martin", phone: "06 34 56 78 90", date: "18/05/2026", color: "from-[#0BA37F] to-[#007B64]" },
  { id: "p5", initials: "LH", name: "Leila Hamel", phone: "06 45 67 89 01", date: "17/05/2026", color: "from-[#FF9A2E] to-[#F36F21]" },
  { id: "p6", initials: "FH", name: "Farid Haddad", phone: "06 56 78 90 12", date: "16/05/2026", color: "from-[#009CA4] to-[#006E78]" },
  { id: "p7", initials: "YM", name: "Yanis Morel", phone: "06 67 89 01 23", date: "15/05/2026", color: "from-[#8068E8] to-[#5942C9]" },
];

const viewTabs: Array<{ id: ViewType; label: string; icon: string }> = [
  { id: "overview", label: "Vue d'ensemble", icon: "▤" },
  { id: "appointments", label: "Rendez-vous", icon: "▣" },
  { id: "history", label: "Historique", icon: "◷" },
];

const REQUEST_STATUS_OVERRIDES_KEY = "uwi_request_status_overrides";

function cx(...classes: Array<string | false | null | undefined>) {
  return classes.filter(Boolean).join(" ");
}

function normalizePhone(value: string) {
  return String(value || "").replace(/[^\d+]/g, "");
}

function initialsFromFullName(name: string) {
  const parts = String(name || "")
    .trim()
    .split(/\s+/)
    .filter(Boolean);
  if (!parts.length) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  const a = parts[0][0];
  const b = parts[parts.length - 1][0];
  return `${a}${b}`.toUpperCase();
}

function formatBytes(value: number) {
  const size = Number(value || 0);
  if (size >= 1024 * 1024) return `${(size / (1024 * 1024)).toFixed(1)} Mo`;
  return `${Math.max(1, Math.round(size / 1024))} Ko`;
}

function normalizeRequestKind(requestId: string) {
  if (requestId.startsWith("req-")) {
    const raw = requestId.slice(4).replace(/^0+/, "") || "0";
    return { kind: "handoff" as const, rawId: raw };
  }
  if (requestId.startsWith("call-")) {
    return { kind: "call" as const, rawId: requestId.slice(5) };
  }
  return { kind: "unknown" as const, rawId: requestId };
}

function toStatusLabel(statusRaw: "processed" | "cancelled") {
  return statusRaw === "cancelled" ? "Annulée" : "Traitée";
}

function isTerminalLabel(label: string) {
  const normalized = String(label || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase();
  return normalized.includes("annule") || normalized.includes("traite");
}

function persistRequestStatusOverride(requestId: string, statusRaw: "processed" | "cancelled") {
  if (typeof window === "undefined") return;
  let current: Record<string, { status_raw: string; updated_at: string }> = {};
  try {
    const parsed = JSON.parse(window.localStorage.getItem(REQUEST_STATUS_OVERRIDES_KEY) || "{}");
    if (parsed && typeof parsed === "object") current = parsed;
  } catch {
    current = {};
  }
  current[requestId] = {
    status_raw: statusRaw,
    updated_at: new Date().toISOString(),
  };
  window.localStorage.setItem(REQUEST_STATUS_OVERRIDES_KEY, JSON.stringify(current));
  window.dispatchEvent(new Event("uwi:request-status-updated"));
}

function Toast({ message }: { message: string }) {
  if (!message) return null;
  return (
    <div className="fixed right-6 top-5 z-50 rounded-2xl bg-[#0A1628] px-4 py-3 text-sm font-bold text-white shadow-2xl">
      {message}
    </div>
  );
}

function HeaderAction({
  children,
  variant = "blue",
  onClick,
}: {
  children: React.ReactNode;
  variant?: "blue" | "green" | "purple" | "gray";
  onClick: () => void;
}) {
  const variants = {
    blue: "border-[#8DD8E3] text-[#007E8C] hover:bg-[#E8F8FA]",
    green: "border-[#8DE4AB] text-[#13A146] hover:bg-[#EEFFF4]",
    purple: "border-[#C7A4FF] text-[#7B3DFF] hover:bg-[#F7F0FF]",
    gray: "border-[#DDE7F1] text-[#475569] hover:bg-[#F8FAFC]",
  };

  return (
    <button
      onClick={onClick}
      className={cx(
        "inline-flex h-12 items-center justify-center gap-2 rounded-xl border bg-white px-5 text-sm font-extrabold transition active:scale-[0.98]",
        variants[variant],
      )}
    >
      {children}
    </button>
  );
}

function OutlineTag({ children, tone = "blue" }: { children: React.ReactNode; tone?: "blue" | "red" }) {
  const tones = {
    blue: "border-[#75D3DF] text-[#008EA1]",
    red: "border-[#FF8989] text-[#EE3434]",
  };
  return <span className={cx("rounded-lg border bg-white px-4 py-2 text-sm font-extrabold", tones[tone])}>{children}</span>;
}

function PrimaryCTA({
  children,
  variant = "dark",
  onClick,
}: {
  children: React.ReactNode;
  variant?: "dark" | "note" | "document";
  onClick: () => void;
}) {
  const variants = {
    dark: "bg-gradient-to-br from-[#06355D] to-[#002D4E] text-white shadow-[0_12px_30px_rgba(3,49,82,.20)] hover:brightness-110",
    note: "border border-[#FF9C4B] bg-white text-[#F26C00] hover:bg-[#FFF7EF]",
    document: "border border-[#6AD58B] bg-white text-[#0EA348] hover:bg-[#F0FFF5]",
  };

  return (
    <button
      onClick={onClick}
      className={cx(
        "flex h-16 items-center justify-center gap-3 rounded-2xl px-6 text-base font-black transition active:scale-[0.98]",
        variants[variant],
      )}
    >
      {children}
    </button>
  );
}

function Modal({
  title,
  children,
  onClose,
  width = "max-w-3xl",
}: {
  title: string;
  children: React.ReactNode;
  onClose: () => void;
  width?: string;
}) {
  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-[#0A1628]/35 p-6 backdrop-blur-sm" onClick={onClose}>
      <div onClick={(e) => e.stopPropagation()} className={cx("max-h-[88vh] w-full overflow-auto rounded-[28px] bg-white p-7 shadow-2xl", width)}>
        <div className="mb-6 flex items-center justify-between gap-4">
          <h2 className="text-2xl font-black tracking-tight text-[#0A1628]">{title}</h2>
          <button onClick={onClose} className="grid h-10 w-10 place-items-center rounded-xl border border-[#DDE7F1] text-xl font-black hover:bg-[#F8FAFC]">
            ×
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

export default function PatientDashboardPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [selectedPatientId, setSelectedPatientId] = useState("p1");
  const [filter, setFilter] = useState("Tous");
  const [activeView, setActiveView] = useState<ViewType>("overview");
  const [toast, setToast] = useState("");
  const [modal, setModal] = useState<ModalType>(null);
  const [note, setNote] = useState("");
  const [patientNotes, setPatientNotes] = useState<PatientNote[]>([]);
  const [notesLoading, setNotesLoading] = useState(false);
  const [notesSaving, setNotesSaving] = useState(false);
  const [noteDeletingId, setNoteDeletingId] = useState<number | null>(null);
  const [documents, setDocuments] = useState<PatientDocument[]>([]);
  const [documentsLoading, setDocumentsLoading] = useState(false);
  const [documentsUploading, setDocumentsUploading] = useState(false);
  const [documentDeletingId, setDocumentDeletingId] = useState<number | null>(null);
  const [documentSendingId, setDocumentSendingId] = useState<number | null>(null);
  const [previewDoc, setPreviewDoc] = useState<PatientDocument | null>(null);
  const [previewUrl, setPreviewUrl] = useState("");
  const [patientEmail, setPatientEmail] = useState("");
  const [editingEmail, setEditingEmail] = useState(false);
  const [emailDraft, setEmailDraft] = useState("");
  const [emailSaving, setEmailSaving] = useState(false);
  const [requestStatus, setRequestStatus] = useState("");
  const [requestActionLoading, setRequestActionLoading] = useState<"" | "processed" | "cancelled">("");
  const [tenantPatientNotFound, setTenantPatientNotFound] = useState(false);
  /** Profil réel (API) pour l’en-tête quand on ouvre /patient-dashboard?phone=… ou un numéro reconnu en base. */
  const [urlPatientHero, setUrlPatientHero] = useState<{ name: string; phone: string; initials: string } | null>(null);
  const toastTimerRef = useRef<number | null>(null);

  useEffect(() => {
    return () => {
      if (toastTimerRef.current) window.clearTimeout(toastTimerRef.current);
    };
  }, []);

  const requestContext = useMemo<RequestContext | null>(() => {
    const requestId = (searchParams.get("requestId") || "").trim();
    if (!requestId) return null;
    return {
      id: requestId,
      phone: (searchParams.get("phone") || "").trim(),
      patientName: (searchParams.get("patientName") || "").trim(),
      summary: (searchParams.get("summary") || "Demande transférée par Clara nécessitant une action humaine.").trim(),
      type: (searchParams.get("type") || "Transfert humain").trim(),
      status: (searchParams.get("status") || "À traiter").trim(),
      source: (searchParams.get("source") || "Via transfert").trim(),
      createdAtLabel: (searchParams.get("createdAtLabel") || "Maintenant").trim(),
    };
  }, [searchParams]);

  const phoneFromDashboardUrl = useMemo(() => (searchParams.get("phone") || "").trim(), [searchParams]);
  const isDirectPhoneView = Boolean(phoneFromDashboardUrl);
  const selectedPatient = patients.find((patient) => patient.id === selectedPatientId) || patients[0];
  const activePatientPhone = (phoneFromDashboardUrl || requestContext?.phone || selectedPatient?.phone || "").trim();

  useEffect(() => {
    if (!phoneFromDashboardUrl) setUrlPatientHero(null);
  }, [phoneFromDashboardUrl]);

  const displayHero = useMemo(() => {
    const teal = "from-[#009CA4] to-[#004C69]";
    const slate = "from-slate-400 to-slate-600";
    const loadingGrad = "from-slate-300 to-slate-500";
    if (tenantPatientNotFound) {
      if (isDirectPhoneView) {
        return {
          name: "Aucune fiche pour ce numéro",
          phone: phoneFromDashboardUrl || activePatientPhone,
          initials: "?",
          gradient: slate,
        };
      }
      return {
        name: selectedPatient.name,
        phone: selectedPatient.phone,
        initials: selectedPatient.initials,
        gradient: selectedPatient.color,
      };
    }
    if (urlPatientHero) {
      return { ...urlPatientHero, gradient: teal };
    }
    if (documentsLoading && activePatientPhone) {
      return {
        name: "Chargement…",
        phone: activePatientPhone,
        initials: "…",
        gradient: loadingGrad,
      };
    }
    return {
      name: selectedPatient.name,
      phone: selectedPatient.phone,
      initials: selectedPatient.initials,
      gradient: selectedPatient.color,
    };
  }, [
    tenantPatientNotFound,
    isDirectPhoneView,
    phoneFromDashboardUrl,
    activePatientPhone,
    urlPatientHero,
    documentsLoading,
    selectedPatient,
  ]);

  const filteredPatients = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) return patients;
    return patients.filter((patient) => `${patient.name} ${patient.phone}`.toLowerCase().includes(normalized));
  }, [query]);

  useEffect(() => {
    if (!requestContext) return;
    const requestPhone = normalizePhone(requestContext.phone);
    const requestName = requestContext.patientName.toLowerCase();
    const fromPhone = requestPhone
      ? patients.find((patient) => normalizePhone(patient.phone) === requestPhone)
      : null;
    const fromName = !fromPhone && requestName
      ? patients.find((patient) => patient.name.toLowerCase().includes(requestName))
      : null;
    const found = fromPhone || fromName;
    if (found && found.id !== selectedPatientId) {
      setSelectedPatientId(found.id);
    }
  }, [requestContext, selectedPatientId]);

  useEffect(() => {
    setRequestStatus(requestContext?.status || "");
    setRequestActionLoading("");
  }, [requestContext?.id, requestContext?.status]);

  useEffect(() => {
    let cancelled = false;
    if (!activePatientPhone) {
      setDocuments([]);
      setUrlPatientHero(null);
      setTenantPatientNotFound(false);
      return () => {
        cancelled = true;
      };
    }
    setDocumentsLoading(true);
    api.tenantGetPatient(activePatientPhone)
      .then((res) => {
        if (cancelled) return;
        setTenantPatientNotFound(false);
        const p = res?.patient as Record<string, unknown> | undefined;
        if (p) {
          const name =
            String(p.display_name || p.validated_name || p.raw_name || "Patient").trim() || "Patient";
          const tel = String(p.phone || activePatientPhone).trim();
          setUrlPatientHero({ name, phone: tel, initials: initialsFromFullName(name) });
        } else {
          setUrlPatientHero(null);
        }
        const list = Array.isArray(res?.documents) ? res.documents : [];
        setPatientEmail(String(p?.email || ""));
        setDocuments(
          list.map((item: any) => ({
            id: Number(item.id),
            original_name: String(item.original_name || ""),
            mime_type: String(item.mime_type || ""),
            size_bytes: Number(item.size_bytes || 0),
            created_at: String(item.created_at || ""),
          })),
        );
      })
      .catch((e: unknown) => {
        const status =
          typeof e === "object" && e !== null && "status" in e ? (e as { status?: number }).status : undefined;
        if (!cancelled) setDocuments([]);
        if (!cancelled) setPatientEmail("");
        if (!cancelled) setUrlPatientHero(null);
        if (!cancelled) setTenantPatientNotFound(status === 404);
      })
      .finally(() => {
        if (!cancelled) setDocumentsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [activePatientPhone]);

  useEffect(() => {
    if (!editingEmail) setEmailDraft(patientEmail || "");
  }, [patientEmail, editingEmail]);

  useEffect(() => {
    let cancelled = false;
    if (!activePatientPhone) {
      setPatientNotes([]);
      return () => {
        cancelled = true;
      };
    }
    setNotesLoading(true);
    api.tenantGetPatientNotes(activePatientPhone, "?limit=100")
      .then((res) => {
        if (cancelled) return;
        const items = Array.isArray(res?.items) ? res.items : [];
        setPatientNotes(
          items.map((item: any) => ({
            id: Number(item.id),
            text: String(item.text || ""),
            author: String(item.author || "Cabinet"),
            created_at: String(item.created_at || ""),
          })),
        );
      })
      .catch(() => {
        if (!cancelled) setPatientNotes([]);
      })
      .finally(() => {
        if (!cancelled) setNotesLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [activePatientPhone]);

  const notify = (message: string) => {
    setToast(message);
    if (toastTimerRef.current) window.clearTimeout(toastTimerRef.current);
    toastTimerRef.current = window.setTimeout(() => setToast(""), 1800);
  };

  const saveNote = async () => {
    if (!note.trim()) {
      notify("Ajoute une note avant d'enregistrer");
      return false;
    }
    if (!activePatientPhone) {
      notify("Aucun patient sélectionné");
      return false;
    }
    setNotesSaving(true);
    try {
      const res = await api.tenantCreatePatientNote(activePatientPhone, { text: note.trim(), author: "Praticien" });
      const created = res?.item;
      if (created) {
        setPatientNotes((prev) => [
          {
            id: Number(created.id),
            text: String(created.text || ""),
            author: String(created.author || "Praticien"),
            created_at: String(created.created_at || ""),
          },
          ...prev,
        ]);
      }
      setNote("");
      notify("Note ajoutée au contexte patient");
      return true;
    } catch (e) {
      notify((e as Error)?.message || "Erreur ajout note");
      return false;
    } finally {
      setNotesSaving(false);
    }
  };

  const removeNote = async (noteId: number) => {
    if (!activePatientPhone || !noteId) return;
    setNoteDeletingId(noteId);
    try {
      await api.tenantDeletePatientNote(activePatientPhone, noteId);
      setPatientNotes((prev) => prev.filter((item) => item.id !== noteId));
      notify("Note supprimée");
    } catch (e) {
      notify((e as Error)?.message || "Erreur suppression note");
    } finally {
      setNoteDeletingId(null);
    }
  };

  const uploadDocument = async (file?: File | null) => {
    if (!file) return;
    if (!activePatientPhone) {
      notify("Aucun patient sélectionné");
      return;
    }
    setDocumentsUploading(true);
    try {
      const res = await api.tenantUploadPatientDocument(activePatientPhone, file);
      const created = res?.document;
      if (created) {
        setDocuments((prev) => [
          {
            id: Number(created.id),
            original_name: String(created.original_name || file.name),
            mime_type: String(created.mime_type || file.type || "application/octet-stream"),
            size_bytes: Number(created.size_bytes || file.size || 0),
            created_at: String(created.created_at || ""),
          },
          ...prev,
        ]);
      }
      notify("Document ajouté");
    } catch (e) {
      notify((e as Error)?.message || "Erreur upload document");
    } finally {
      setDocumentsUploading(false);
    }
  };

  const downloadDocument = async (doc: PatientDocument) => {
    if (!activePatientPhone) return;
    try {
      const url = api.tenantDownloadPatientDocument(activePatientPhone, doc.id);
      const res = await fetch(url, { credentials: "include" });
      if (!res.ok) throw new Error("Téléchargement échoué");
      const blob = await res.blob();
      const objectUrl = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = objectUrl;
      a.download = doc.original_name || "document";
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(objectUrl);
    } catch (e) {
      notify((e as Error)?.message || "Erreur téléchargement");
    }
  };

  const openPreview = async (doc: PatientDocument) => {
    if (!activePatientPhone) return;
    const canPreview = doc.mime_type.includes("pdf") || doc.mime_type.startsWith("image/");
    if (!canPreview) {
      await downloadDocument(doc);
      return;
    }
    try {
      const url = api.tenantDownloadPatientDocument(activePatientPhone, doc.id);
      const res = await fetch(url, { credentials: "include" });
      if (!res.ok) throw new Error("Impossible de charger le document");
      const blob = await res.blob();
      const objectUrl = URL.createObjectURL(blob);
      setPreviewDoc(doc);
      setPreviewUrl(objectUrl);
    } catch (e) {
      notify((e as Error)?.message || "Erreur prévisualisation");
    }
  };

  const closePreview = () => {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setPreviewDoc(null);
    setPreviewUrl("");
  };

  const deleteDocument = async (docId: number) => {
    if (!activePatientPhone || !docId) return;
    setDocumentDeletingId(docId);
    try {
      await api.tenantDeletePatientDocument(activePatientPhone, docId);
      setDocuments((prev) => prev.filter((doc) => doc.id !== docId));
      notify("Document supprimé");
    } catch (e) {
      notify((e as Error)?.message || "Erreur suppression document");
    } finally {
      setDocumentDeletingId(null);
    }
  };

  const sendDocument = async (docId: number) => {
    if (!activePatientPhone || !docId) return;
    if (!patientEmail) {
      notify("Ajoute d'abord l'email du patient");
      return;
    }
    setDocumentSendingId(docId);
    try {
      await api.tenantSendPatientDocument(activePatientPhone, docId);
      notify(`Document envoyé à ${patientEmail}`);
    } catch (e) {
      notify((e as Error)?.message || "Erreur envoi email");
    } finally {
      setDocumentSendingId(null);
    }
  };

  const saveEmail = async () => {
    if (!activePatientPhone) {
      notify("Aucun patient sélectionné");
      return;
    }
    setEmailSaving(true);
    try {
      await api.tenantUpdatePatient(activePatientPhone, { email: emailDraft.trim() });
      setPatientEmail(emailDraft.trim());
      setEditingEmail(false);
      notify(emailDraft.trim() ? "Email enregistré" : "Email supprimé");
    } catch (e) {
      notify((e as Error)?.message || "Erreur mise à jour email");
    } finally {
      setEmailSaving(false);
    }
  };

  const updateRequestStatus = async (nextStatus: "processed" | "cancelled") => {
    if (!requestContext?.id) return;
    const info = normalizeRequestKind(requestContext.id);
    if (info.kind === "call" && nextStatus === "cancelled") {
      notify("Annulation indisponible pour ce type de demande");
      return;
    }
    setRequestActionLoading(nextStatus);
    try {
      if (info.kind === "handoff") {
        await api.tenantUpdateHandoff(info.rawId, { status: nextStatus });
      } else if (info.kind === "call") {
        await api.tenantUpdateCallFollowup(info.rawId, { followup_state: "processed" });
      } else {
        throw new Error("Demande introuvable");
      }
      const nextLabel = toStatusLabel(nextStatus);
      setRequestStatus(nextLabel);
      persistRequestStatusOverride(requestContext.id, nextStatus);
      const next = new URLSearchParams(searchParams);
      next.set("status", nextLabel);
      setSearchParams(next, { replace: true });
      notify(nextStatus === "cancelled" ? "Demande annulée" : "Demande marquée traitée");
    } catch (e) {
      notify((e as Error)?.message || "Erreur de mise à jour");
    } finally {
      setRequestActionLoading("");
    }
  };

  return (
    <div className="min-h-screen bg-[#F7FAFC] text-[#0A1628]">
      <Toast message={toast} />

      <div className="grid min-h-screen grid-cols-[330px_minmax(900px,1fr)]">
        <aside className="border-r border-[#E5EDF5] bg-white px-6 py-8">
          <div className="mb-5 flex items-center justify-between">
            <h2 className="text-2xl font-black">Patients</h2>
            <span className="rounded-xl bg-[#EEF6FA] px-3 py-1.5 text-sm font-black text-[#1C4B6B]">208</span>
          </div>

          <div className="relative mb-5">
            <span className="absolute left-4 top-1/2 -translate-y-1/2 text-lg text-[#8D9AAF]">⌕</span>
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Rechercher un patient..."
              className="h-12 w-full rounded-xl border border-[#DDE7F1] bg-white pl-11 pr-4 text-sm outline-none transition placeholder:text-[#9AA8BB] focus:border-[#009CA4] focus:ring-4 focus:ring-[#009CA4]/10"
            />
          </div>

          <div className="mb-6 flex flex-wrap gap-2">
            {[["Tous", "208"], ["À traiter", "12"], ["Nouveaux", "15"]].map(([label, count]) => (
              <button
                key={label}
                onClick={() => setFilter(label)}
                className={cx(
                  "rounded-lg border px-3.5 py-2 text-xs font-black transition",
                  filter === label
                    ? "border-[#009CA4] bg-white text-[#008EA1] shadow-sm"
                    : label === "À traiter"
                      ? "border-[#FFE4D1] bg-[#FFF7F1] text-[#EF6C00]"
                      : "border-[#E2EAF4] bg-[#F9FCFF] text-[#1A72C5]",
                )}
              >
                {label} <span className="ml-1">{count}</span>
              </button>
            ))}
          </div>

          <div className="overflow-hidden rounded-3xl border border-[#E5EDF5] bg-white shadow-sm">
            {filteredPatients.map((patient) => {
              const selected = patient.id === selectedPatientId;
              return (
                <button
                  key={patient.id}
                  onClick={() => setSelectedPatientId(patient.id)}
                  className={cx(
                    "flex w-full items-center gap-4 border-b border-[#EEF3F8] p-4 text-left transition last:border-b-0",
                    selected ? "bg-[#EAF8FC] ring-1 ring-inset ring-[#BFEAF0]" : "hover:bg-[#F8FBFD]",
                  )}
                >
                  <div className={cx("grid h-12 w-12 shrink-0 place-items-center rounded-xl bg-gradient-to-br text-lg font-black text-white shadow-sm", patient.color)}>
                    {patient.initials}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-sm font-black">{patient.name}</div>
                    <div className="mt-1 text-sm text-[#53647F]">{patient.phone}</div>
                  </div>
                  <div className="text-xs font-semibold text-[#53647F]">{patient.date}</div>
                </button>
              );
            })}

            <button onClick={() => notify("Liste complète des patients ouverte")} className="flex h-16 w-full items-center justify-center gap-3 text-sm font-black text-[#007E8C] hover:bg-[#F8FBFD]">
              Voir tous les patients <span className="text-xl">›</span>
            </button>
          </div>
        </aside>

        <main className="overflow-y-auto px-8 py-6">
          {tenantPatientNotFound ? (
            <div className="mb-6 rounded-2xl border border-amber-200 bg-amber-50 px-5 py-4 text-sm text-amber-950 shadow-sm">
              <span className="font-black">Aucune fiche patient trouvée pour ce numéro sur le dashboard.</span> Retournez à la liste
              {" "}
              <button
                type="button"
                onClick={() => navigate("/app/patients")}
                className="font-black text-amber-800 underline underline-offset-2 hover:text-amber-900"
              >
                Patients
              </button>
              {" "}
              ou créez-la depuis l&apos;
              <button
                type="button"
                onClick={() => navigate("/app/agenda")}
                className="font-black text-amber-800 underline underline-offset-2 hover:text-amber-900"
              >
                agenda
              </button>
              .
            </div>
          ) : null}
          <section className="rounded-[28px] border border-[#E2EAF4] bg-white p-7 shadow-[0_18px_45px_rgba(10,22,40,0.06)]">
            <div className="flex items-start justify-between gap-8">
              <div className="flex min-w-0 gap-6">
                <div className={cx("grid h-32 w-32 shrink-0 place-items-center rounded-3xl bg-gradient-to-br text-5xl font-black text-white shadow-[8px_10px_0_rgba(0,156,164,0.12)]", displayHero.gradient)}>
                  {displayHero.initials}
                </div>

                <div className="min-w-0">
                  <div className="mb-3 flex flex-wrap items-center gap-4">
                    <h1 className="text-4xl font-black tracking-tight">{displayHero.name}</h1>
                    <span className="rounded-lg bg-[#E6FAED] px-3 py-2 text-sm font-black text-[#0BA64B]">● Actif</span>
                  </div>

                  <div className="mb-5 flex flex-wrap gap-x-8 gap-y-2 text-sm font-semibold text-[#52637C]">
                    <span>☎ {displayHero.phone}</span>
                    {editingEmail ? (
                      <span className="inline-flex items-center gap-2">
                        <span>✉</span>
                        <input
                          value={emailDraft}
                          onChange={(event) => setEmailDraft(event.target.value)}
                          placeholder="email@cabinet.fr"
                          className="h-8 rounded-lg border border-[#DDE7F1] px-2 text-sm font-semibold text-[#0A1628] outline-none focus:border-[#009CA4]"
                        />
                        <button type="button" onClick={saveEmail} disabled={emailSaving} className="rounded-lg bg-[#009CA4] px-2 py-1 text-xs font-black text-white disabled:opacity-60">
                          {emailSaving ? "..." : "OK"}
                        </button>
                        <button type="button" onClick={() => setEditingEmail(false)} className="rounded-lg border border-[#DDE7F1] px-2 py-1 text-xs font-black text-[#475569]">
                          Annuler
                        </button>
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-2">
                        <span>✉ {patientEmail || "Aucun email"}</span>
                        <button type="button" onClick={() => setEditingEmail(true)} className="rounded-lg border border-[#DDE7F1] px-2 py-1 text-xs font-black text-[#475569] hover:bg-[#F8FAFC]">
                          {patientEmail ? "Modifier" : "Ajouter"}
                        </button>
                      </span>
                    )}
                  </div>

                  <div className="flex flex-wrap gap-3">
                    <OutlineTag>Patient régulier</OutlineTag>
                    <OutlineTag>Préférence matin</OutlineTag>
                    <OutlineTag>SMS préféré</OutlineTag>
                    <OutlineTag tone="red">Risque no-show</OutlineTag>
                  </div>
                </div>
              </div>

              <div className="flex shrink-0 flex-wrap justify-end gap-3">
                <HeaderAction
                  onClick={() => {
                    const t = normalizePhone(displayHero.phone);
                    if (t) window.location.href = `tel:${t}`;
                    else notify("Numéro absent pour passer un appel.");
                  }}
                >
                  ☎ Appeler
                </HeaderAction>
                <HeaderAction variant="green" onClick={() => notify("WhatsApp ouvert")}>☘ WhatsApp</HeaderAction>
                <HeaderAction variant="purple" onClick={() => notify("SMS ouvert")}>▣ SMS</HeaderAction>
                <HeaderAction variant="gray" onClick={() => notify("Menu patient ouvert")}>•••</HeaderAction>
              </div>
            </div>
          </section>

          <section className="mt-5 rounded-[26px] border border-[#E2EAF4] bg-white shadow-sm">
            <div className="flex border-b border-[#EEF3F8]">
              {viewTabs.map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActiveView(tab.id)}
                  className={cx(
                    "relative flex h-16 items-center gap-3 px-8 text-sm font-black transition",
                    activeView === tab.id ? "text-[#008EA1]" : "text-[#42536E] hover:bg-[#F8FBFD]",
                  )}
                >
                  <span className="text-xl">{tab.icon}</span>
                  {tab.label}
                  {activeView === tab.id && <span className="absolute bottom-0 left-0 right-0 h-1 bg-[#009CA4]" />}
                </button>
              ))}
            </div>

            <div className="grid grid-cols-3 gap-4 p-5">
              <PrimaryCTA onClick={() => setModal("profile")}>✎ Voir le profil détaillé</PrimaryCTA>
              <PrimaryCTA variant="note" onClick={() => setModal("addNote")}>✎ Ajouter une note</PrimaryCTA>
              <PrimaryCTA variant="document" onClick={() => setModal("addDocument")}>▤ Ajouter un document</PrimaryCTA>
            </div>
          </section>

          {requestContext && (
            <section className="mt-6 rounded-[28px] border border-[#FFD9B8] bg-[#FFF7F0] p-6 shadow-sm">
              <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h2 className="text-2xl font-black text-[#0A1628]">Demande à traiter</h2>
                  <p className="mt-1 text-sm font-semibold text-[#6B5A4A]">
                    Demande transférée car elle nécessite une action humaine
                  </p>
                </div>
                <button
                  onClick={() => {
                    const next = new URLSearchParams(searchParams);
                    [
                      "requestId",
                      "phone",
                      "patientName",
                      "summary",
                      "type",
                      "status",
                      "source",
                      "createdAtLabel",
                    ].forEach((key) => next.delete(key));
                    setSearchParams(next, { replace: true });
                  }}
                  className="rounded-xl border border-[#F2C59F] bg-white px-4 py-2 text-xs font-black text-[#9A5A1C] hover:bg-[#FFF4EA]"
                >
                  Masquer
                </button>
              </div>

              <div className="grid grid-cols-2 gap-3 text-sm">
                <div className="rounded-xl border border-[#F4E1CF] bg-white p-3">
                  <div className="text-xs font-bold text-[#8B735D]">Type de demande</div>
                  <div className="mt-1 font-black text-[#0A1628]">{requestContext.type}</div>
                </div>
                <div className="rounded-xl border border-[#F4E1CF] bg-white p-3">
                  <div className="text-xs font-bold text-[#8B735D]">Statut</div>
                  <div className="mt-1 font-black text-[#0A1628]">{requestStatus || requestContext.status}</div>
                </div>
                <div className="rounded-xl border border-[#F4E1CF] bg-white p-3">
                  <div className="text-xs font-bold text-[#8B735D]">Date/heure de transfert</div>
                  <div className="mt-1 font-black text-[#0A1628]">{requestContext.createdAtLabel}</div>
                </div>
                <div className="rounded-xl border border-[#F4E1CF] bg-white p-3">
                  <div className="text-xs font-bold text-[#8B735D]">Source</div>
                  <div className="mt-1 font-black text-[#0A1628]">{requestContext.source}</div>
                </div>
              </div>

              <div className="mt-3 rounded-xl border border-[#F4E1CF] bg-white p-4">
                <div className="text-xs font-bold uppercase tracking-wide text-[#8B735D]">Résumé généré par Clara</div>
                <p className="mt-2 text-sm leading-7 text-[#334155]">{requestContext.summary}</p>
              </div>

              <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3">
                <button onClick={() => notify("Action: Rappeler le patient")} className="rounded-xl bg-[#009CA4] px-4 py-3 text-sm font-black text-white hover:bg-[#00838A]">Rappeler le patient</button>
                <button onClick={() => notify("Action: Assigner au médecin")} className="rounded-xl border border-[#DDE7F1] bg-white px-4 py-3 text-sm font-black text-[#0A1628] hover:bg-[#F8FAFC]">Assigner au médecin</button>
                <button onClick={() => notify("Action: Planifier un créneau")} className="rounded-xl border border-[#DDE7F1] bg-white px-4 py-3 text-sm font-black text-[#0A1628] hover:bg-[#F8FAFC]">Planifier un créneau</button>
                <button onClick={() => setModal("addNote")} className="rounded-xl border border-[#DDE7F1] bg-white px-4 py-3 text-sm font-black text-[#0A1628] hover:bg-[#F8FAFC]">Ajouter une note</button>
                <button
                  onClick={() => updateRequestStatus("processed")}
                  disabled={!!requestActionLoading || isTerminalLabel(requestStatus || requestContext.status)}
                  className={cx(
                    "rounded-xl border border-[#A7F3D0] bg-[#ECFDF5] px-4 py-3 text-sm font-black text-[#047857] sm:col-span-2",
                    !!requestActionLoading || isTerminalLabel(requestStatus || requestContext.status) ? "cursor-not-allowed opacity-60" : "hover:bg-[#DDFBEF]",
                  )}
                >
                  {requestActionLoading === "processed" ? "Traitement..." : "Marquer comme traitée"}
                </button>
                <button
                  onClick={() => updateRequestStatus("cancelled")}
                  disabled={!!requestActionLoading || isTerminalLabel(requestStatus || requestContext.status)}
                  className={cx(
                    "rounded-xl border border-[#CBD5E1] bg-[#F8FAFC] px-4 py-3 text-sm font-black text-[#475569] sm:col-span-3",
                    !!requestActionLoading || isTerminalLabel(requestStatus || requestContext.status) ? "cursor-not-allowed opacity-60" : "hover:bg-[#F1F5F9]",
                  )}
                >
                  {requestActionLoading === "cancelled" ? "Annulation..." : "Annuler la demande"}
                </button>
              </div>
            </section>
          )}

          {activeView === "overview" && (
            <div className="mt-6 grid grid-cols-[1.25fr_0.85fr] gap-6">
              <div className="space-y-6">
                <section className="rounded-[28px] border border-[#E2EAF4] bg-white p-6 shadow-sm">
                  <div className="mb-5 flex items-center justify-between gap-4">
                    <h2 className="flex items-center gap-3 text-xl font-black">▣ Prochain rendez-vous</h2>
                    <button onClick={() => setModal("history")} className="rounded-xl border border-[#91D9E3] px-4 py-2 text-sm font-black text-[#008EA1] hover:bg-[#E9FAFC]">
                      ◴ Voir l'historique complet
                    </button>
                  </div>

                  <div className="flex items-center gap-7">
                    <div className="grid h-28 w-24 shrink-0 place-items-center rounded-2xl bg-gradient-to-br from-[#009CA4] to-[#004C69] text-center text-white shadow-[8px_8px_0_rgba(0,156,164,0.12)]">
                      <div>
                        <div className="text-4xl font-black">21</div>
                        <div className="mt-1 text-base">mai 2026</div>
                        <div className="mt-1 text-base font-black">JEU.</div>
                      </div>
                    </div>

                    <div className="min-w-0 flex-1">
                      <div className="mb-4 flex flex-wrap items-center gap-6">
                        <div className="text-4xl font-black">10:30 <span className="text-base font-semibold text-[#64748B]">(20 min)</span></div>
                        <div className="h-8 w-px bg-[#D9E3EF]" />
                        <div className="text-xl font-black">Dr Martin</div>
                        <span className="rounded-lg bg-[#E6FAED] px-3 py-2 text-sm font-black text-[#0BA64B]">Confirmé</span>
                      </div>

                      <div className="grid grid-cols-4 gap-3 text-sm">
                        <div><div className="mb-1 text-xs font-bold text-[#7D8CA5]">Motif</div><div className="font-black">Douleurs thoraciques</div></div>
                        <div><div className="mb-1 text-xs font-bold text-[#7D8CA5]">Source</div><div className="font-black">Pris par Clara (UWi)</div></div>
                        <div><div className="mb-1 text-xs font-bold text-[#7D8CA5]">Préférence</div><div className="font-black">Matin</div></div>
                        <div><div className="mb-1 text-xs font-bold text-[#7D8CA5]">Canal</div><div className="font-black">Téléphone</div></div>
                      </div>

                      <div className="mt-5 flex flex-wrap gap-3">
                        <button onClick={() => notify("Déplacement du RDV ouvert")} className="rounded-xl border border-[#72CDE0] px-4 py-2 text-sm font-black text-[#008EA1] hover:bg-[#E9FAFC]">▣ Déplacer le RDV</button>
                        <button onClick={() => notify("Annulation du RDV demandée")} className="rounded-xl border border-[#FF9B9B] px-4 py-2 text-sm font-black text-[#FF3030] hover:bg-[#FFF1F1]">♲ Annuler le RDV</button>
                        <button onClick={() => notify("Agenda ouvert")} className="rounded-xl border border-[#B6C3D7] px-4 py-2 text-sm font-black text-[#53647F] hover:bg-[#F8FAFC]">▣ Voir l'agenda</button>
                      </div>
                    </div>
                  </div>
                </section>

                <section className="rounded-[28px] bg-gradient-to-br from-[#062E53] via-[#023E63] to-[#007B88] p-6 text-white shadow-[0_20px_45px_rgba(0,66,90,0.22)]">
                  <h2 className="mb-5 text-2xl font-black">☆ Contexte patient</h2>
                  <div className="grid grid-cols-2 gap-6">
                    <div>
                      <div className="mb-4 flex items-center justify-between">
                        <div className="text-sm font-black uppercase tracking-wide text-[#11D6DB]">● Résumé Clara</div>
                        <div className="text-sm italic text-white/60">Généré par IA</div>
                      </div>

                      <p className="text-[17px] leading-8 text-white/95">
                        {displayHero.name} contacte principalement le cabinet par téléphone. Les notes et documents ci-dessous sont
                        synchronisés avec votre espace cabinet lorsque le numéro ou la fiche correspondent en base.
                      </p>

                      <p className="mt-5 text-sm italic text-white/65">Mis à jour · Aujourd'hui à 14:32</p>
                    </div>

                    <div className="border-l border-white/25 pl-6">
                      <h3 className="mb-4 text-xl font-black text-white">✎ Notes de l'équipe</h3>

                      <div className="space-y-4">
                        {notesLoading ? (
                          <div className="text-sm text-white/70">Chargement des notes...</div>
                        ) : patientNotes.length === 0 ? (
                          <div className="text-sm text-white/70">Aucune note pour ce patient.</div>
                        ) : (
                          patientNotes.slice(0, 4).map((item) => (
                            <div key={item.id} className="border-b border-white/20 pb-4">
                              <div className="text-base font-semibold">♡ {item.text}</div>
                              <div className="mt-1 flex items-center justify-between text-sm text-white/60">
                                <span>{item.author} · {new Date(item.created_at).toLocaleDateString("fr-FR")}</span>
                                <button
                                  type="button"
                                  onClick={() => removeNote(item.id)}
                                  disabled={noteDeletingId === item.id}
                                  className="rounded border border-white/25 px-2 py-0.5 text-xs font-bold text-white/80 hover:bg-white/10 disabled:opacity-50"
                                >
                                  {noteDeletingId === item.id ? "..." : "Supprimer"}
                                </button>
                              </div>
                            </div>
                          ))
                        )}
                      </div>

                      <textarea
                        value={note}
                        onChange={(event) => setNote(event.target.value)}
                        placeholder="Ajouter une note..."
                        className="mt-4 h-16 w-full resize-none rounded-xl border border-white/20 bg-white px-4 py-3 text-[#0A1628] outline-none focus:ring-4 focus:ring-[#00C4CC]/25"
                      />
                      <button onClick={saveNote} disabled={notesSaving} className="mt-3 rounded-xl bg-[#00A5AE] px-7 py-3 text-sm font-black text-white shadow-lg hover:bg-[#00949C] disabled:opacity-60">
                        {notesSaving ? "Enregistrement..." : "Enregistrer"}
                      </button>
                    </div>
                  </div>
                </section>
              </div>

              <aside className="space-y-6">
                <section className="rounded-[28px] border border-[#E2EAF4] bg-white p-7 shadow-sm">
                  <div className="mb-5 flex items-center justify-between">
                    <h2 className="text-2xl font-black"><span className="text-[#FF8A00]">ϟ</span> À traiter <span className="ml-2 rounded-full bg-[#FFF1E8] px-2 py-1 text-sm text-[#FF6B00]">2</span></h2>
                    <button onClick={() => notify("Actions à traiter ouvertes")} className="text-sm font-black text-[#008EA1]">Voir tout ›</button>
                  </div>

                  <div className="space-y-4">
                    <button onClick={() => notify("Rappel automatique à confirmer")} className="flex w-full items-center gap-4 rounded-2xl border border-[#EEF3F8] p-4 text-left hover:bg-[#F8FBFD]">
                      <div className="grid h-12 w-12 place-items-center rounded-xl bg-[#FFF5F5] text-xl">🗓</div>
                      <div className="flex-1"><div className="font-black">Confirmer rappel automatique</div><div className="mt-1 text-sm text-[#61708B]">Échéance : 17/05/2026</div></div>
                      <span className="rounded-lg bg-[#FFF1EA] px-3 py-2 text-xs font-black text-[#FF4B3E]">À faire</span>
                    </button>

                    <button onClick={() => notify("Document demandé ouvert")} className="flex w-full items-center gap-4 rounded-2xl border border-[#EEF3F8] p-4 text-left hover:bg-[#F8FBFD]">
                      <div className="grid h-12 w-12 place-items-center rounded-xl bg-[#F1F5FF] text-xl">🔒</div>
                      <div className="flex-1"><div className="font-black">Document demandé</div><div className="mt-1 text-sm text-[#61708B]">Échéance : 18/05/2026</div></div>
                      <span className="rounded-lg bg-[#FFF2E3] px-3 py-2 text-xs font-black text-[#EF6C00]">En attente</span>
                    </button>
                  </div>
                </section>
              </aside>
            </div>
          )}

          {activeView === "appointments" && (
            <section className="mt-6 rounded-[28px] border border-[#E2EAF4] bg-white p-8 shadow-sm">
              <h2 className="mb-5 text-2xl font-black">Rendez-vous du patient</h2>
              <div className="space-y-4">
                {[
                  ["21/05/2026", "10:30", "Confirmé", "Douleurs thoraciques"],
                  ["12/04/2026", "09:30", "Consulte", "Suivi"],
                  ["28/03/2026", "10:00", "Annulé par patient", "Contrôle"],
                ].map(([date, hour, status, reason]) => (
                  <div key={`${date}-${hour}`} className="grid grid-cols-[120px_90px_1fr_160px] items-center rounded-2xl border border-[#EEF3F8] p-4 text-sm">
                    <b>{date}</b><b>{hour}</b><span>{reason}</span><span className="rounded-lg bg-[#F2F8FA] px-3 py-2 text-center font-black text-[#007E8C]">{status}</span>
                  </div>
                ))}
              </div>
            </section>
          )}

          {activeView === "history" && (
            <section className="mt-6 rounded-[28px] border border-[#E2EAF4] bg-white p-8 shadow-sm">
              <h2 className="mb-5 text-2xl font-black">Historique des interactions</h2>
              <HistoryList />
            </section>
          )}
        </main>
      </div>

      {modal === "profile" && (
        <Modal title="Profil détaillé" onClose={() => setModal(null)} width="max-w-2xl">
          <div className="grid grid-cols-2 gap-4 text-sm">
            {[
              ["Patient depuis", "12/02/2026"],
              ["ID patient", "ID_PP_000512"],
              ["Date de naissance", "14/06/1982 (43 ans)"],
              ["Préférence contact", "Téléphone"],
              ["Langue", "Français"],
              ["Médecin associé", "Dr Martin"],
            ].map(([label, value]) => (
              <div key={label} className="rounded-2xl bg-[#F8FBFD] p-4">
                <div className="mb-1 text-xs font-bold text-[#7D8CA5]">{label}</div>
                <div className="font-black">{value}</div>
              </div>
            ))}
          </div>
          <div className="mt-6 flex gap-3">
            <button onClick={() => notify("Modification du profil ouverte")} className="flex-1 rounded-xl bg-[#009CA4] px-4 py-3 font-black text-white">Modifier le profil</button>
            <button onClick={() => notify("Suppression du profil demandée")} className="flex-1 rounded-xl border border-red-300 px-4 py-3 font-black text-red-600">Supprimer</button>
          </div>
        </Modal>
      )}

      {modal === "addNote" && (
        <Modal title="Ajouter une note" onClose={() => setModal(null)} width="max-w-xl">
          <textarea
            autoFocus
            value={note}
            onChange={(event) => setNote(event.target.value)}
            placeholder="Ex. Préfère les rendez-vous le matin, ne pas appeler après 18h..."
            className="h-40 w-full resize-none rounded-2xl border border-[#DDE7F1] p-4 outline-none focus:border-[#009CA4] focus:ring-4 focus:ring-[#009CA4]/10"
          />
          <button
            onClick={async () => {
              const ok = await saveNote();
              if (ok) setModal(null);
            }}
            disabled={notesSaving}
            className="mt-4 w-full rounded-xl bg-[#009CA4] px-4 py-3 font-black text-white disabled:opacity-60"
          >
            {notesSaving ? "Enregistrement..." : "Enregistrer la note"}
          </button>
        </Modal>
      )}

      {modal === "addDocument" && (
        <Modal title="Ajouter un document" onClose={() => setModal(null)} width="max-w-xl">
          <div className="rounded-3xl border-2 border-dashed border-[#BFE6EC] bg-[#F7FCFD] p-8 text-center">
            <div className="mb-3 text-4xl">▤</div>
            <div className="text-lg font-black">Déposer un document</div>
            <p className="mt-2 text-sm text-[#61708B]">Justificatif, courrier ou document administratif lié à la demande.</p>
            <label className="mt-5 inline-flex cursor-pointer rounded-xl border border-[#009CA4] bg-white px-5 py-3 font-black text-[#008EA1]">
              {documentsUploading ? "Envoi..." : "Choisir un fichier"}
              <input
                type="file"
                disabled={documentsUploading}
                accept=".pdf,.jpg,.jpeg,.png,.doc,.docx,.xls,.xlsx,.txt"
                onChange={(event) => {
                  const file = event.target.files?.[0];
                  uploadDocument(file);
                  event.target.value = "";
                }}
                className="hidden"
              />
            </label>
          </div>

          <div className="mt-5">
            <h4 className="mb-2 text-sm font-black text-[#334155]">Documents patient</h4>
            {documentsLoading ? (
              <div className="rounded-xl border border-[#E2E8F0] bg-[#F8FAFC] px-4 py-3 text-sm text-[#64748B]">Chargement...</div>
            ) : documents.length === 0 ? (
              <div className="rounded-xl border border-[#E2E8F0] bg-[#F8FAFC] px-4 py-3 text-sm text-[#64748B]">Aucun document pour ce patient.</div>
            ) : (
              <div className="max-h-64 space-y-2 overflow-auto pr-1">
                {documents.map((doc) => {
                  const canPreview = doc.mime_type.includes("pdf") || doc.mime_type.startsWith("image/");
                  return (
                    <div key={doc.id} className="flex items-center justify-between gap-3 rounded-xl border border-[#E2E8F0] bg-white px-3 py-2">
                      <div className="min-w-0 flex-1">
                        <div className="truncate text-sm font-bold text-[#0A1628]">{doc.original_name}</div>
                        <div className="text-xs text-[#64748B]">{formatBytes(doc.size_bytes)} · {doc.created_at ? new Date(doc.created_at).toLocaleDateString("fr-FR") : "maintenant"}</div>
                      </div>
                      <div className="flex items-center gap-2">
                        {canPreview ? (
                          <button type="button" onClick={() => openPreview(doc)} className="rounded-lg border border-[#DDE7F1] px-2 py-1 text-xs font-black text-[#0A1628] hover:bg-[#F8FAFC]">Voir</button>
                        ) : null}
                        <button type="button" onClick={() => downloadDocument(doc)} className="rounded-lg border border-[#DDE7F1] px-2 py-1 text-xs font-black text-[#0A1628] hover:bg-[#F8FAFC]">Télécharger</button>
                        <button
                          type="button"
                          onClick={() => sendDocument(doc.id)}
                          disabled={documentSendingId === doc.id || !patientEmail}
                          className="rounded-lg border border-[#86EFAC] px-2 py-1 text-xs font-black text-[#15803D] hover:bg-[#F0FDF4] disabled:opacity-50"
                          title={patientEmail ? `Envoyer à ${patientEmail}` : "Ajoute un email patient"}
                        >
                          {documentSendingId === doc.id ? "..." : "Envoyer"}
                        </button>
                        <button
                          type="button"
                          onClick={() => deleteDocument(doc.id)}
                          disabled={documentDeletingId === doc.id}
                          className="rounded-lg border border-[#FCA5A5] px-2 py-1 text-xs font-black text-[#B91C1C] hover:bg-[#FEF2F2] disabled:opacity-50"
                        >
                          {documentDeletingId === doc.id ? "..." : "Supprimer"}
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </Modal>
      )}

      {modal === "history" && (
        <Modal title="Historique complet" onClose={() => setModal(null)} width="max-w-4xl">
          <HistoryList extended />
        </Modal>
      )}

      {previewDoc && previewUrl && (
        <Modal title={previewDoc.original_name} onClose={closePreview} width="max-w-4xl">
          <div className="mb-3 flex justify-end">
            <button
              type="button"
              onClick={() => sendDocument(previewDoc.id)}
              disabled={documentSendingId === previewDoc.id || !patientEmail}
              className="rounded-lg border border-[#86EFAC] px-3 py-1.5 text-xs font-black text-[#15803D] hover:bg-[#F0FDF4] disabled:opacity-50"
            >
              {documentSendingId === previewDoc.id ? "Envoi..." : "Envoyer par email"}
            </button>
          </div>
          {previewDoc.mime_type.includes("pdf") ? (
            <iframe src={previewUrl} title={previewDoc.original_name} className="h-[70vh] w-full rounded-xl border border-[#E2E8F0]" />
          ) : previewDoc.mime_type.startsWith("image/") ? (
            <img src={previewUrl} alt={previewDoc.original_name} className="max-h-[70vh] w-full rounded-xl border border-[#E2E8F0] object-contain" />
          ) : (
            <div className="rounded-xl border border-[#E2E8F0] bg-[#F8FAFC] px-4 py-3 text-sm text-[#64748B]">
              Aperçu indisponible pour ce type de fichier.
            </div>
          )}
        </Modal>
      )}
    </div>
  );
}

function HistoryList({ extended = false }: { extended?: boolean }) {
  const rows: Array<[string, string, string, string, string, "green" | "orange"]> = [
    ["17/05/2026", "09:36", "Appel sortant", "Rappel de rendez-vous pour le 21 mai 2026 à 10:30.", "Traité automatiquement", "green"],
    ["15/05/2026", "14:22", "SMS sortant", "Rappel automatique de rendez-vous.", "Traité automatiquement", "green"],
    ["12/05/2026", "08:47", "Appel entrant", "Demande de report au 26/05 à 09:30.", "Action humaine requise", "orange"],
    ["10/05/2026", "11:05", "Document reçu", "Justificatif d'assurance ajouté au dossier.", "Traité automatiquement", "green"],
  ];

  return (
    <div className="space-y-0 overflow-hidden rounded-2xl border border-[#EEF3F8] bg-white">
      {rows.slice(0, extended ? rows.length : 3).map(([date, hour, type, result, status, tone]) => (
        <div key={`${date}-${hour}`} className="grid grid-cols-[16px_110px_150px_1fr_180px] items-center gap-4 border-b border-[#EEF3F8] p-4 last:border-b-0">
          <span className={cx("h-3 w-3 rounded-full", tone === "green" ? "bg-[#18C765]" : "bg-[#FF9E18]")} />
          <div className="text-sm text-[#61708B]"><b>{date}</b><br />{hour}</div>
          <div className="font-black">{type}</div>
          <div className="text-sm text-[#53647F]">{result}</div>
          <span className={cx("rounded-lg px-3 py-2 text-center text-xs font-black", tone === "green" ? "bg-[#E8FAF0] text-[#0B9445]" : "bg-[#FFF1DE] text-[#D96B00]")}>{status}</span>
        </div>
      ))}
    </div>
  );
}
