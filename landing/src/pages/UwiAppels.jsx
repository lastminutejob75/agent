import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  AlertCircle,
  Calendar,
  Check,
  ChevronDown,
  ChevronRight,
  Clock3,
  FileText,
  Filter,
  Headphones,
  Info,
  LayoutList,
  Mic2,
  PenLine,
  Phone,
  PhoneCall,
  PhoneOff,
  Play,
  Search,
  User,
  UserPlus,
  X,
} from "lucide-react";
import { useNavigate, useSearchParams } from "react-router-dom";
import CreatePatientFromCallModal from "../components/calls/CreatePatientFromCallModal.jsx";
import PatientDuplicateBanner from "../components/patients/PatientDuplicateBanner.jsx";
import { api } from "../lib/api.js";
import { useCalls } from "../lib/useCalls.js";
import { useNoteDictation, appendDictatedText } from "../lib/useNoteDictation.js";
import { canCreatePatientFromCall, getCallCounts } from "../lib/callJournal.utils.js";
import {
  buildCallPatientApiPayload,
  buildPatientCreateFormFromCall,
  computePatientCreateFieldErrors,
  isPatientCreateSubmitBlocked,
  PATIENT_CREATE_FORM_EMPTY,
  usePatientCreateDuplicateCheck,
  validatePatientCreateFormForSubmit,
} from "../lib/patientCreateForm.js";
import {
  checkPatientDuplicates,
  formatPatientDuplicateConflict,
  hasBlockingPatientDuplicate,
  parsePatientDuplicateError,
} from "../lib/patientDuplicateCheck.js";

const C = {
  teal: "#009CA4",
  tealDark: "#007F87",
  tealSoft: "#E6F7F8",
  tealBorder: "#B8E6E9",
  tealBg: "#F0FAFB",
  navy: "#0A1628",
  navyHover: "#162238",
  orange: "#FF7A1A",
  orangeSoft: "#FFF3EA",
  red: "#EF4444",
  redSoft: "#FEF2F2",
  green: "#16A34A",
  greenSoft: "#EAFAF0",
  blue: "#2563EB",
  blueSoft: "#EEF5FF",
  ink: "#334155",
  muted: "#7A8A9E",
  subtle: "#94A3B8",
  line: "#E2E8F0",
  lineSoft: "#EDF2F7",
  bg: "#F5F9FA",
  surface: "#FAFCFD",
  hover: "#F1F5F9",
  white: "#FFFFFF",
};

const typeConfig = {
  "rendez-vous": { label: "Rendez-vous", icon: Calendar, color: C.teal, bg: C.tealSoft },
  "a-rappeler": { label: "À rappeler", icon: PhoneCall, color: C.orange, bg: C.orangeSoft },
  information: { label: "Information", icon: Info, color: C.blue, bg: C.blueSoft },
  "appel-manque": { label: "Appel manqué", icon: PhoneOff, color: C.red, bg: C.redSoft },
  annulation: { label: "Annulation", icon: Calendar, color: C.orange, bg: C.orangeSoft },
  deplacement: { label: "Déplacement", icon: Calendar, color: C.teal, bg: C.tealSoft },
  sensible: { label: "Sensible", icon: AlertCircle, color: C.red, bg: C.redSoft },
};

const tabsData = [
  { key: "tous", label: "Tous" },
  { key: "a-traiter", label: "À traiter" },
  { key: "rendez-vous", label: "Rendez-vous" },
  { key: "sans-fiche", label: "Sans fiche" },
  { key: "historique", label: "Historique" },
];

function normalizePhone(value) {
  return String(value || "").replace(/[^\d+]/g, "");
}

function splitName(value) {
  const full = String(value || "").trim();
  if (!full) return { firstName: "", lastName: "" };
  const parts = full.split(/\s+/);
  if (parts.length === 1) return { firstName: "", lastName: parts[0] };
  return { firstName: parts.slice(0, -1).join(" "), lastName: parts.slice(-1)[0] };
}

function composePatientName({ firstName, lastName }) {
  return [String(firstName || "").trim(), String(lastName || "").trim()].filter(Boolean).join(" ").trim();
}

function Hoverable({ style, hoverStyle, as: Tag = "div", children, ...rest }) {
  const [hovered, setHovered] = useState(false);
  return (
    <Tag
      style={{ ...style, ...(hovered ? hoverStyle : {}) }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      {...rest}
    >
      {children}
    </Tag>
  );
}

function KpiCard({ icon: Icon, value, label, sublabel, accent = C.teal, onClick, selected = false }) {
  return (
    <Hoverable
      as={onClick ? "button" : "div"}
      type={onClick ? "button" : undefined}
      onClick={onClick}
      style={{
        borderRadius: 16,
        border: `1px solid ${selected ? `${accent}55` : C.line}`,
        background: C.white,
        padding: 20,
        boxShadow: selected ? `0 0 0 2px ${accent}22` : "0 1px 3px rgba(10,22,40,0.04)",
        transition: "box-shadow 0.2s ease, border-color 0.2s ease",
        cursor: onClick ? "pointer" : "default",
        width: "100%",
        textAlign: "left",
      }}
      hoverStyle={{ boxShadow: "0 8px 24px rgba(10,22,40,0.06)" }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
        <div
          style={{
            width: 56,
            height: 56,
            borderRadius: 16,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            background: `${accent}14`,
            color: accent,
            flexShrink: 0,
          }}
        >
          <Icon size={26} strokeWidth={2.2} />
        </div>
        <div>
          <div style={{ fontSize: 32, fontWeight: 800, lineHeight: 1, color: C.navy }}>{value}</div>
          <div style={{ marginTop: 4, fontSize: 14, fontWeight: 700, color: C.navy }}>{label}</div>
          <div style={{ fontSize: 12, color: C.muted }}>{sublabel}</div>
        </div>
      </div>
    </Hoverable>
  );
}

function PatientAvatar({ patient, selected }) {
  if (!patient.known) {
    return (
      <div
        style={{
          width: 40,
          height: 40,
          borderRadius: "50%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: selected ? "rgba(255,255,255,0.8)" : C.hover,
          flexShrink: 0,
        }}
      >
        {patient.masked ? <PhoneOff size={17} color={C.muted} /> : <User size={17} color={C.muted} />}
      </div>
    );
  }
  return (
    <div
      style={{
        width: 40,
        height: 40,
        borderRadius: "50%",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: C.tealSoft,
        color: C.teal,
        fontSize: 13,
        fontWeight: 800,
        flexShrink: 0,
      }}
    >
      {patient.initials || "PT"}
    </div>
  );
}

function TypeBadge({ type }) {
  const cfg = typeConfig[type] || typeConfig.information;
  const Icon = cfg.icon;
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 6,
        borderRadius: 8,
        padding: "4px 10px",
        fontSize: 12,
        fontWeight: 700,
        background: cfg.bg,
        color: cfg.color,
        whiteSpace: "nowrap",
      }}
    >
      <Icon size={13} strokeWidth={2.4} />
      {cfg.label}
    </span>
  );
}

function RowAction({ call, onPrimaryAction }) {
  if (canCreatePatientFromCall(call)) {
    return (
      <Hoverable
        as="button"
        onClick={(event) => {
          event.stopPropagation();
          onPrimaryAction(call);
        }}
        style={{
          display: "inline-flex",
          alignItems: "center",
          borderRadius: 8,
          border: `1px solid ${C.teal}`,
          background: C.tealSoft,
          padding: "6px 12px",
          fontSize: 12,
          fontWeight: 700,
          color: C.teal,
          cursor: "pointer",
          whiteSpace: "nowrap",
        }}
        hoverStyle={{ background: "#D0F0F2" }}
      >
        <UserPlus size={14} style={{ marginRight: 6 }} />
        Créer une fiche
      </Hoverable>
    );
  }
  return (
    <Hoverable
      as="button"
      onClick={(event) => {
        event.stopPropagation();
        onPrimaryAction(call);
      }}
      style={{
        display: "inline-flex",
        alignItems: "center",
        borderRadius: 8,
        border: `1px solid ${C.line}`,
        background: C.white,
        padding: "6px 12px",
        fontSize: 12,
        fontWeight: 700,
        color: C.navy,
        cursor: "pointer",
        whiteSpace: "nowrap",
      }}
      hoverStyle={{ background: C.bg }}
    >
      Voir le détail
      <ChevronRight size={14} style={{ marginLeft: 4 }} />
    </Hoverable>
  );
}

function CallGroupBadge({ count }) {
  if (!count || count < 2) return null;
  return (
    <span
      style={{
        flexShrink: 0,
        borderRadius: 99,
        background: C.tealSoft,
        color: C.tealDark,
        padding: "1px 7px",
        fontSize: 11,
        fontWeight: 800,
        lineHeight: 1.6,
      }}
    >
      {count} appels
    </span>
  );
}

function CallRow({ call, selected, onSelect, onPrimaryAction, compact = false, groupCount = 1 }) {
  const isSelected = selected?.id === call.id;

  if (compact) {
    return (
      <Hoverable
        as="button"
        type="button"
        onClick={() => onSelect(call)}
        style={{
          width: "100%",
          border: "none",
          borderBottom: `1px solid ${C.lineSoft}`,
          padding: "14px 14px 12px",
          textAlign: "left",
          cursor: "pointer",
          transition: "all 0.1s ease",
          background: isSelected ? C.tealBg : C.white,
          boxShadow: isSelected ? `inset 3px 0 0 ${C.teal}` : "none",
        }}
        hoverStyle={isSelected ? {} : { background: C.surface }}
      >
        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 10 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10, minWidth: 0 }}>
            <PatientAvatar patient={call.patient} selected={isSelected} />
            <div style={{ minWidth: 0 }}>
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 6,
                  fontSize: 14,
                  fontWeight: 700,
                  color: C.navy,
                  minWidth: 0,
                }}
              >
                <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {call.patient.name}
                </span>
                <CallGroupBadge count={groupCount} />
              </div>
              <div
                style={{
                  marginTop: 1,
                  fontSize: 12,
                  color: C.muted,
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                }}
              >
                {call.patient.phone || "—"}
              </div>
            </div>
          </div>
          <div style={{ textAlign: "right", flexShrink: 0 }}>
            <span style={{ display: "block", fontSize: 11, fontWeight: 600, color: C.subtle }}>{call.date}</span>
            <span style={{ fontSize: 13, fontWeight: 700, color: C.navy }}>{call.time}</span>
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10, marginTop: 10 }}>
          <TypeBadge type={call.type} />
          <div style={{ display: "flex", justifyContent: "flex-end" }}>
            <RowAction call={call} onPrimaryAction={onPrimaryAction} />
          </div>
        </div>

        <div
          style={{
            marginTop: 10,
            fontSize: 13,
            lineHeight: 1.45,
            color: C.ink,
            minWidth: 0,
            overflow: "hidden",
            display: "-webkit-box",
            WebkitLineClamp: 2,
            WebkitBoxOrient: "vertical",
          }}
        >
          {call.summary}
        </div>
      </Hoverable>
    );
  }

  return (
    <Hoverable
      as="button"
      type="button"
      onClick={() => onSelect(call)}
      style={{
        display: "grid",
        gridTemplateColumns: "1.4fr 1fr 2.2fr 0.7fr 1.1fr",
        alignItems: "center",
        gap: 16,
        width: "100%",
        border: "none",
        borderBottom: `1px solid ${C.lineSoft}`,
        padding: "14px 20px",
        textAlign: "left",
        cursor: "pointer",
        transition: "all 0.1s ease",
        background: isSelected ? C.tealBg : C.white,
        boxShadow: isSelected ? `inset 3px 0 0 ${C.teal}` : "none",
      }}
      hoverStyle={isSelected ? {} : { background: C.surface }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 12, minWidth: 0 }}>
        <PatientAvatar patient={call.patient} selected={isSelected} />
        <div style={{ minWidth: 0 }}>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 6,
              fontSize: 14,
              fontWeight: 700,
              color: C.navy,
              minWidth: 0,
            }}
          >
            <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              {call.patient.name}
            </span>
            <CallGroupBadge count={groupCount} />
          </div>
          <div
            style={{
              fontSize: 12,
              color: C.muted,
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}
          >
            {call.patient.phone || "—"}
          </div>
        </div>
      </div>

      <div>
        <TypeBadge type={call.type} />
      </div>

      <div
        style={{
          fontSize: 13,
          lineHeight: 1.5,
          color: C.ink,
          minWidth: 0,
          overflow: "hidden",
          display: "-webkit-box",
          WebkitLineClamp: 2,
          WebkitBoxOrient: "vertical",
        }}
      >
        {call.summary}
      </div>

      <div style={{ textAlign: "right" }}>
        <span style={{ display: "block", fontSize: 11, fontWeight: 600, color: C.subtle }}>{call.date}</span>
        <span style={{ fontSize: 14, fontWeight: 700, color: C.navy }}>{call.time}</span>
      </div>

      <div style={{ display: "flex", justifyContent: "flex-end" }}>
        <RowAction call={call} onPrimaryAction={onPrimaryAction} />
      </div>
    </Hoverable>
  );
}

function EmptyDetail({ compact = false }) {
  if (compact) return null;
  return (
    <aside
      style={{
        position: "sticky",
        top: 0,
        width: 340,
        minWidth: 340,
        height: "100vh",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        borderLeft: `1px solid ${C.line}`,
        background: C.white,
        padding: "0 24px",
      }}
    >
      <div
        style={{
          width: 64,
          height: 64,
          borderRadius: 16,
          background: C.hover,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <Phone size={24} color="#C5CDD6" />
      </div>
      <p style={{ marginTop: 16, textAlign: "center", fontSize: 14, color: C.muted, lineHeight: 1.5 }}>
        Sélectionnez un appel
        <br />
        pour voir le détail
      </p>
    </aside>
  );
}

function InfoLine({ icon: Icon, label, value }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 12, fontSize: 13 }}>
      <Icon size={15} color={C.subtle} style={{ flexShrink: 0 }} />
      <span style={{ width: 52, flexShrink: 0, color: C.muted }}>{label}</span>
      <span style={{ fontWeight: 700, color: C.navy }}>{value}</span>
    </div>
  );
}

function StatusBadge({ status }) {
  const isTraite = status === "traité" || status === "résolu";
  return (
    <span
      style={{
        display: "inline-flex",
        borderRadius: 6,
        padding: "2px 8px",
        fontSize: 12,
        fontWeight: 700,
        background: isTraite ? C.greenSoft : C.orangeSoft,
        color: isTraite ? C.green : C.orange,
      }}
    >
      {status}
    </span>
  );
}

function PanelAction({ icon: Icon, label, right, variant = "default", onClick, asLink = false, href }) {
  const isPrimary = variant === "primary";
  const baseStyle = {
    display: "flex",
    width: "100%",
    alignItems: "center",
    gap: 12,
    borderRadius: 12,
    border: `1px solid ${isPrimary ? C.teal : C.line}`,
    background: isPrimary ? C.teal : C.white,
    color: isPrimary ? C.white : C.navy,
    padding: "12px 16px",
    fontSize: 13,
    fontWeight: 700,
    cursor: "pointer",
    textAlign: "left",
    transition: "all 0.1s ease",
    boxShadow: isPrimary ? "0 4px 12px rgba(0,156,164,0.2)" : "none",
  };
  const hoverStyle = {
    background: isPrimary ? C.tealDark : C.bg,
    borderColor: isPrimary ? C.tealDark : "#D0D8E0",
  };

  if (asLink) {
    return (
      <Hoverable as="a" href={href} onClick={onClick} style={baseStyle} hoverStyle={hoverStyle}>
        <Icon size={16} />
        <span>{label}</span>
        {right && <span style={{ marginLeft: "auto", fontSize: 12, fontWeight: 600, opacity: 0.6 }}>{right}</span>}
      </Hoverable>
    );
  }

  return (
    <Hoverable as="button" type="button" onClick={onClick} style={baseStyle} hoverStyle={hoverStyle}>
      <Icon size={16} />
      <span>{label}</span>
      {right && <span style={{ marginLeft: "auto", fontSize: 12, fontWeight: 600, opacity: 0.6 }}>{right}</span>}
    </Hoverable>
  );
}

function DetailPanel({ call, onClose, onCreatePatient, onOpenPatient, onMarkHandled, onAddNote, compact = false }) {
  const [noteOpen, setNoteOpen] = useState(false);
  const [noteDraft, setNoteDraft] = useState("");
  const [noteDictError, setNoteDictError] = useState("");
  const noteDictation = useNoteDictation({
    onText: (text) => setNoteDraft((prev) => appendDictatedText(prev, text)),
    onError: (msg) => setNoteDictError(msg || ""),
  });
  if (!call) return <EmptyDetail compact={compact} />;

  const canCreatePatient = canCreatePatientFromCall(call);
  const canRecall = Boolean(call.patient.phone) && !call.patient.masked;

  async function handleSaveNote() {
    if (!noteDraft.trim()) return;
    await onAddNote(call, noteDraft.trim());
    setNoteDraft("");
    setNoteOpen(false);
  }

  const panelStyle = compact
    ? {
        position: "fixed",
        top: 0,
        right: 0,
        width: "100vw",
        height: "100vh",
        display: "flex",
        flexDirection: "column",
        background: C.white,
        overflowY: "auto",
        zIndex: 80,
      }
    : {
        position: "sticky",
        top: 0,
        width: 340,
        minWidth: 340,
        height: "100vh",
        display: "flex",
        flexDirection: "column",
        borderLeft: `1px solid ${C.line}`,
        background: C.white,
        overflowY: "auto",
      };

  return (
    <aside
      style={panelStyle}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "16px 20px",
          borderBottom: `1px solid ${C.lineSoft}`,
        }}
      >
        <span style={{ fontSize: 13, fontWeight: 800, color: C.navy }}>Détail de l'appel</span>
        <Hoverable
          as="button"
          type="button"
          onClick={onClose}
          style={{
            border: "none",
            background: "none",
            borderRadius: 8,
            padding: 6,
            cursor: "pointer",
            color: C.subtle,
            display: "flex",
          }}
          hoverStyle={{ background: C.hover, color: C.navy }}
        >
          <X size={16} />
        </Hoverable>
      </div>

      <div style={{ flex: 1, padding: 20 }}>
        <div
          style={{
            borderRadius: 16,
            border: `1px solid ${C.line}`,
            background: C.white,
            padding: 20,
            textAlign: "center",
            boxShadow: "0 2px 8px rgba(10,22,40,0.04)",
          }}
        >
          <div
            style={{
              width: 72,
              height: 72,
              borderRadius: "50%",
              background: C.tealSoft,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              margin: "0 auto",
            }}
          >
            {call.patient.known ? (
              <span style={{ fontSize: 24, fontWeight: 800, color: C.teal }}>{call.patient.initials || "PT"}</span>
            ) : call.patient.masked ? (
              <PhoneOff size={28} color={C.muted} />
            ) : (
              <User size={28} color={C.muted} />
            )}
          </div>
          <h2 style={{ marginTop: 12, fontSize: 18, fontWeight: 800, color: C.navy }}>{call.patient.name}</h2>
          <p style={{ marginTop: 2, fontSize: 14, color: C.muted }}>{call.patient.phone || "Numéro non disponible"}</p>

          {!call.patient.known && (
            <div
              style={{
                display: "inline-flex",
                alignItems: "center",
                marginTop: 12,
                borderRadius: 99,
                background: C.orangeSoft,
                padding: "4px 12px",
                fontSize: 11,
                fontWeight: 700,
                color: C.orange,
              }}
            >
              <AlertCircle size={12} style={{ marginRight: 6 }} />
              Aucun dossier patient lié
            </div>
          )}

          {canCreatePatient && (
            <Hoverable
              as="button"
              type="button"
              onClick={() => onCreatePatient(call)}
              style={{
                display: "flex",
                width: "100%",
                alignItems: "center",
                justifyContent: "center",
                marginTop: 16,
                borderRadius: 12,
                border: "none",
                background: C.teal,
                color: C.white,
                padding: "12px 16px",
                fontSize: 14,
                fontWeight: 800,
                cursor: "pointer",
                boxShadow: "0 4px 12px rgba(0,156,164,0.2)",
              }}
              hoverStyle={{ background: C.tealDark }}
            >
              <UserPlus size={16} style={{ marginRight: 8 }} />
              Créer une fiche patient
            </Hoverable>
          )}
        </div>

        <section style={{ marginTop: 20 }}>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              marginBottom: 10,
              fontSize: 13,
              fontWeight: 800,
              color: C.navy,
            }}
          >
            <Headphones size={15} color={C.teal} />
            Résumé de Clara
          </div>
          <div
            style={{
              borderRadius: 12,
              border: `1px solid ${C.tealBorder}`,
              background: C.tealBg,
              padding: "14px 16px",
              fontSize: 13,
              lineHeight: 1.6,
              color: C.navy,
            }}
          >
            {call.claraResume || call.summary || "Aucun résumé Clara disponible."}
          </div>
        </section>

        <section style={{ marginTop: 20 }}>
          <div style={{ marginBottom: 10, fontSize: 13, fontWeight: 800, color: C.navy }}>Informations</div>
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              gap: 10,
              borderRadius: 12,
              border: `1px solid ${C.line}`,
              background: C.white,
              padding: "14px 16px",
            }}
          >
            <InfoLine icon={Clock3} label="Date" value={`${call.date} · ${call.time}`} />
            <InfoLine icon={Mic2} label="Durée" value={call.duration || "—"} />
            <div style={{ display: "flex", alignItems: "center", gap: 12, fontSize: 13 }}>
              <FileText size={15} color={C.subtle} style={{ flexShrink: 0 }} />
              <span style={{ width: 52, flexShrink: 0, color: C.muted }}>Statut</span>
              <StatusBadge status={call.status} />
            </div>
            <InfoLine icon={User} label="Patient" value={call.patient.known ? "Fiche existante" : "Non rattaché"} />
          </div>
        </section>

        <section style={{ marginTop: 20 }}>
          <div style={{ marginBottom: 10, fontSize: 13, fontWeight: 800, color: C.navy }}>Actions</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {call.recording && (
              <PanelAction
                icon={Play}
                label="Écouter l'enregistrement"
                right={call.duration}
                onClick={() => window.open(call.recordingUrl, "_blank", "noopener,noreferrer")}
              />
            )}
            {call.patient.known && (
              <PanelAction
                icon={User}
                label="Voir la fiche patient"
                variant="primary"
                onClick={() => onOpenPatient(call)}
              />
            )}
            {canRecall && (
              <PanelAction
                asLink
                icon={PhoneCall}
                label="Rappeler le patient"
                href={`tel:${normalizePhone(call.patient.phone)}`}
              />
            )}
            <PanelAction icon={PenLine} label="Ajouter une note" onClick={() => setNoteOpen((prev) => !prev)} />
            {noteOpen ? (
              <div style={{ borderRadius: 12, border: `1px solid ${C.line}`, padding: 10, background: C.white }}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, marginBottom: 8 }}>
                  <span style={{ fontSize: 11, fontWeight: 700, color: C.muted }}>Écrivez ou dictez la note</span>
                  {noteDictation.supported ? (
                    <button
                      type="button"
                      onClick={() => { setNoteDictError(""); noteDictation.toggle(); }}
                      disabled={noteDictation.transcribing}
                      aria-pressed={noteDictation.recording}
                      style={{
                        display: "inline-flex",
                        alignItems: "center",
                        gap: 6,
                        borderRadius: 8,
                        border: `1px solid ${noteDictation.recording ? C.red : "#6941C6"}`,
                        background: noteDictation.recording ? C.redSoft : C.white,
                        color: noteDictation.recording ? C.red : "#5B34B0",
                        padding: "6px 10px",
                        fontSize: 12,
                        fontWeight: 800,
                        cursor: noteDictation.transcribing ? "default" : "pointer",
                        opacity: noteDictation.transcribing ? 0.6 : 1,
                      }}
                    >
                      <Mic2 size={13} />
                      {noteDictation.transcribing ? "Transcription…" : noteDictation.recording ? "Arrêter" : "Dicter"}
                    </button>
                  ) : null}
                </div>
                <textarea
                  value={noteDraft}
                  onChange={(event) => setNoteDraft(event.target.value)}
                  placeholder="Ajouter une note... (ou dictez-la à la voix)"
                  style={{
                    width: "100%",
                    minHeight: 72,
                    resize: "vertical",
                    borderRadius: 8,
                    border: `1px solid ${C.line}`,
                    padding: 10,
                    fontSize: 13,
                    outline: "none",
                  }}
                />
                {noteDictation.recording ? (
                  <div style={{ marginTop: 6, fontSize: 12, fontWeight: 700, color: C.red }}>
                    Dictée en cours… parlez, puis cliquez sur « Arrêter ».
                  </div>
                ) : noteDictation.transcribing ? (
                  <div style={{ marginTop: 6, fontSize: 12, fontWeight: 700, color: C.teal }}>Transcription en cours…</div>
                ) : noteDictError ? (
                  <div style={{ marginTop: 6, fontSize: 12, fontWeight: 700, color: C.red }}>{noteDictError}</div>
                ) : null}
                <button
                  type="button"
                  onClick={handleSaveNote}
                  disabled={noteDictation.recording || noteDictation.transcribing}
                  style={{
                    marginTop: 8,
                    width: "100%",
                    borderRadius: 8,
                    border: `1px solid ${C.line}`,
                    background: C.bg,
                    padding: "8px 10px",
                    fontSize: 12,
                    fontWeight: 700,
                    color: C.navy,
                    cursor: noteDictation.recording || noteDictation.transcribing ? "default" : "pointer",
                    opacity: noteDictation.recording || noteDictation.transcribing ? 0.6 : 1,
                  }}
                >
                  Enregistrer la note
                </button>
              </div>
            ) : null}
            {(call.status === "à traiter" || call.status === "manqué") && (
              <PanelAction icon={Check} label="Marquer comme traité" onClick={() => onMarkHandled(call)} />
            )}
          </div>
        </section>
      </div>
    </aside>
  );
}

function exportCallsToCsv(calls) {
  const rows = [["Date", "Heure", "Patient", "Téléphone", "Type", "Statut", "Résumé"]];
  for (const call of calls || []) {
    rows.push([
      call.date || "",
      call.time || "",
      call.patient?.name || "",
      call.patient?.phone || "",
      call.type || "",
      call.status || "",
      String(call.summary || "").replace(/\s+/g, " ").trim(),
    ]);
  }
  const escape = (value) => {
    const s = String(value ?? "");
    return /[",\n;]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  const csv = "\uFEFF" + rows.map((r) => r.map(escape).join(";")).join("\r\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `appels-${new Date().toISOString().slice(0, 10)}.csv`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

export default function UwiAppels() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { calls, loading, error, selectCall, markAsHandled, createPatientFromCall, addCallNote } = useCalls({ days: 30 });
  const [activeTab, setActiveTab] = useState("tous");
  const [selectedCall, setSelectedCall] = useState(null);
  const [query, setQuery] = useState("");
  const [searchFocused, setSearchFocused] = useState(false);
  const [expandedGroups, setExpandedGroups] = useState({});
  const [compactFilters, setCompactFilters] = useState(
    typeof window !== "undefined" ? window.innerWidth < 1024 : false,
  );
  const [compactHeader, setCompactHeader] = useState(
    typeof window !== "undefined" ? window.innerWidth < 1024 : false,
  );
  const [filterOpen, setFilterOpen] = useState(false);
  const [subFilters, setSubFilters] = useState({
    status: "all",
    type: "all",
    patient: "all",
    period: "all",
  });
  const [toast, setToast] = useState("");
  const toastTimerRef = useRef(0);
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [createLoading, setCreateLoading] = useState(false);
  const [createForm, setCreateForm] = useState(PATIENT_CREATE_FORM_EMPTY);
  const [createConflicts, setCreateConflicts] = useState([]);

  const createFieldErrors = useMemo(() => computePatientCreateFieldErrors(createForm), [createForm]);
  const createSubmitBlocked = useMemo(
    () => isPatientCreateSubmitBlocked(createFieldErrors, createConflicts),
    [createFieldErrors, createConflicts],
  );
  const handleCreateConflicts = useCallback((conflicts) => {
    setCreateConflicts(conflicts);
  }, []);

  usePatientCreateDuplicateCheck({
    enabled: createModalOpen,
    phone: createForm.phone,
    email: createForm.email,
    onConflicts: handleCreateConflicts,
  });

  const counts = useMemo(() => {
    const c = getCallCounts(calls);
    const rappel = calls.filter((call) => call.type === "a-rappeler").length;
    return {
      total: c.total,
      rdv: c.appointmentsTaken,
      toTreat: c.toProcess,
      rappel,
      unknown: c.unknownWithPhone,
    };
  }, [calls]);

  const filteredCalls = useMemo(() => {
    const q = query.trim().toLowerCase();
    const now = Date.now();
    const periodMs =
      subFilters.period === "today"
        ? 24 * 60 * 60 * 1000
        : subFilters.period === "7d"
          ? 7 * 24 * 60 * 60 * 1000
          : subFilters.period === "30d"
            ? 30 * 24 * 60 * 60 * 1000
            : 0;
    return calls
      .filter((call) => {
        if (activeTab === "a-traiter") return call.status === "à traiter" || call.status === "manqué";
        if (activeTab === "rendez-vous") return call.type === "rendez-vous";
        if (activeTab === "sans-fiche") return !call.patient?.known;
        if (activeTab === "historique") return call.status === "traité" || call.status === "résolu";
        return true;
      })
      .filter((call) => {
        if (subFilters.status !== "all" && call.status !== subFilters.status) return false;
        if (subFilters.type !== "all" && call.type !== subFilters.type) return false;
        if (subFilters.patient === "known" && !call.patient?.known) return false;
        if (subFilters.patient === "unknown" && call.patient?.known) return false;
        if (periodMs > 0) {
          const ts = new Date(String(call.createdAt || call.raw?.last_event_at || call.raw?.started_at || "")).getTime();
          if (Number.isFinite(ts)) {
            if (now - ts > periodMs) return false;
          }
        }
        return true;
      })
      .filter((call) => {
        if (!q) return true;
        return [call.patient?.name, call.patient?.phone, call.summary, call.type]
          .filter(Boolean)
          .join(" ")
          .toLowerCase()
          .includes(q);
      });
  }, [activeTab, query, calls, subFilters]);

  // Regroupe les appels consécutifs d'un même numéro (ex. un inconnu qui
  // rappelle 3 fois) en une seule ligne dépliable, pour réduire le bruit.
  const groupedCalls = useMemo(() => {
    const groups = [];
    let lastKey = null;
    for (const call of filteredCalls) {
      const phone = normalizePhone(call.patient?.phone || call.phone || "");
      const key = phone && !call.patient?.masked ? `tel:${phone}` : `solo:${call.id}`;
      if (key === lastKey && groups.length) {
        groups[groups.length - 1].items.push(call);
      } else {
        groups.push({ key, lead: call, items: [call] });
        lastKey = key;
      }
    }
    return groups.map((g) => ({ ...g, count: g.items.length }));
  }, [filteredCalls]);

  const toggleGroup = useCallback((key) => {
    setExpandedGroups((prev) => ({ ...prev, [key]: !prev[key] }));
  }, []);

  const activeFilterCount = useMemo(
    () => Object.values(subFilters).filter((value) => value !== "all").length,
    [subFilters],
  );

  useEffect(() => {
    const type = String(searchParams.get("type") || "").trim().toLowerCase();
    const filter = String(searchParams.get("filter") || "").trim().toLowerCase();
    const period = String(searchParams.get("period") || "").trim().toLowerCase();
    if (filter === "rdv" || type === "rendez-vous") {
      setActiveTab("rendez-vous");
      setSubFilters({ status: "all", type: "all", patient: "all", period: period === "today" ? "today" : "all" });
      return;
    }
    if (type === "annulation") {
      setActiveTab("tous");
      setSubFilters({
        status: "all",
        type: "annulation",
        patient: "all",
        period: period === "today" ? "today" : "all",
      });
    }
  }, [searchParams]);

  useEffect(() => {
    if (typeof window === "undefined") return undefined;
    const onResize = () => {
      setCompactFilters(window.innerWidth < 1024);
      setCompactHeader(window.innerWidth < 1024);
    };
    onResize();
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  useEffect(() => {
    if (typeof document === "undefined") return undefined;
    if (!(compactHeader && selectedCall)) return undefined;
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prevOverflow;
    };
  }, [compactHeader, selectedCall]);

  useEffect(() => {
    if (typeof window === "undefined") return undefined;
    if (!(compactHeader && selectedCall)) return undefined;
    const onKeyDown = (event) => {
      if (event.key === "Escape") {
        setSelectedCall(null);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [compactHeader, selectedCall]);

  function notify(message) {
    setToast(message);
    if (toastTimerRef.current) window.clearTimeout(toastTimerRef.current);
    toastTimerRef.current = window.setTimeout(() => setToast(""), 2200);
  }

  function resetFilters() {
    setSubFilters({ status: "all", type: "all", patient: "all", period: "all" });
    if (compactFilters) setFilterOpen(false);
  }

  function updateSubFilter(key, value) {
    setSubFilters((prev) => ({ ...prev, [key]: value }));
    if (compactFilters) setFilterOpen(false);
  }

  function applyKpiFilter(key) {
    if (key === "total") {
      setActiveTab("tous");
      resetFilters();
      return;
    }
    if (key === "rdv") {
      setActiveTab("rendez-vous");
      resetFilters();
      return;
    }
    if (key === "rappel") {
      setActiveTab("tous");
      setSubFilters({ status: "all", type: "a-rappeler", patient: "all", period: "all" });
      if (compactFilters) setFilterOpen(false);
    }
  }

  async function handleSelect(call) {
    setSelectedCall(call);
    await selectCall(call.id);
  }

  function openCreatePatientModal(call) {
    setCreateForm(buildPatientCreateFormFromCall(call));
    setCreateConflicts([]);
    setCreateModalOpen(true);
  }

  async function handleCreatePatientSubmit() {
    const currentCallId = createForm.callId;
    if (!currentCallId) return;

    const validated = validatePatientCreateFormForSubmit(createForm);
    if (!validated.ok) {
      notify(validated.message || "Complétez le formulaire.");
      return;
    }

    let conflicts = createConflicts;
    try {
      const dupRes = await checkPatientDuplicates({
        phone: validated.phone,
        email: validated.email,
      });
      conflicts = Array.isArray(dupRes?.conflicts) ? dupRes.conflicts : [];
      setCreateConflicts(conflicts);
    } catch {
      /* conserve les conflits affichés */
    }
    if (hasBlockingPatientDuplicate(conflicts)) {
      notify(formatPatientDuplicateConflict(conflicts[0]) || "Doublon téléphone ou e-mail.");
      return;
    }

    const payload = buildCallPatientApiPayload(createForm, {
      validatedName: validated.name,
      rawName: validated.name,
    });
    if (!payload.ok) {
      notify(payload.message || "Formulaire incomplet.");
      return;
    }

    setCreateLoading(true);
    try {
      const result = await createPatientFromCall(currentCallId, payload.body);
      const linkedPhone = String(result?.patient?.phone || validated.phone).trim();
      if (!linkedPhone) throw new Error("Profil créé mais téléphone introuvable.");

      const noteText = createForm.initialNote.trim();
      if (noteText) {
        try {
          await api.tenantCreatePatientNote(linkedPhone, { text: noteText, author: "Cabinet" });
        } catch {
          await addCallNote(currentCallId, noteText);
        }
      }

      // Recopie la note déjà saisie sur l'appel (avant création de la fiche)
      // vers la nouvelle fiche patient, puis vide la note de suivi de l'appel
      // pour qu'aucune note ne reste « bloquée » côté appel.
      try {
        const callDetail = await api.tenantGetCallDetail(currentCallId);
        const existingCallNote = String(callDetail?.followup_notes || "").trim();
        if (existingCallNote && existingCallNote !== noteText) {
          await api.tenantCreatePatientNote(linkedPhone, { text: existingCallNote, author: "Cabinet" });
          await api.tenantUpdateCallFollowup(currentCallId, {
            followup_state: callDetail?.followup_state || "new",
            notes: "",
          });
        }
      } catch {
        /* best-effort : en cas d'échec la note reste consultable côté appel */
      }

      await api.tenantGetPatient(linkedPhone);
      setCreateModalOpen(false);
      setCreateConflicts([]);
      notify("Profil patient créé.");
      await selectCall(currentCallId);
      setSelectedCall((prev) =>
        prev?.id === currentCallId
          ? {
              ...prev,
              phone: linkedPhone,
              patient: {
                ...prev.patient,
                known: true,
                masked: false,
                name: validated.name,
                phone: linkedPhone,
              },
            }
          : prev,
      );
    } catch (e) {
      const dup = parsePatientDuplicateError(e);
      notify(dup.message || e?.message || "Impossible de créer le profil patient.");
    } finally {
      setCreateLoading(false);
    }
  }

  async function handleMarkHandled(call) {
    try {
      await markAsHandled(call.id);
      notify("Appel marqué comme traité.");
      if (selectedCall?.id === call.id) {
        setSelectedCall((prev) => (prev ? { ...prev, status: "résolu" } : prev));
      }
    } catch (e) {
      notify(e?.message || "Impossible de marquer comme traité.");
    }
  }

  async function handleAddNote(call, noteText) {
    try {
      await addCallNote(call.id, noteText);
      notify("Note ajoutée.");
    } catch (e) {
      notify(e?.message || "Impossible d'ajouter la note.");
    }
  }

  function handlePrimaryAction(call) {
    if (canCreatePatientFromCall(call)) {
      openCreatePatientModal(call);
      return;
    }
    handleSelect(call);
  }

  return (
    <div className="uwi-appels-page" style={{ minHeight: "100%", background: C.bg, color: C.navy }}>
      <style>
        {`
          .uwi-tabs-scroll {
            -ms-overflow-style: none;
            scrollbar-width: none;
          }
          .uwi-tabs-scroll::-webkit-scrollbar {
            display: none;
            width: 0;
            height: 0;
          }
          @media (max-width: 1024px) {
            .uwi-appels-main { padding: 14px 12px 24px !important; }
          }
          @media (max-width: 760px) {
            .uwi-appels-page-header { display: none !important; }
            .uwi-appels-main { padding: 10px 10px 20px !important; }
            .uwi-appels-list-wrap { margin: 0 0 16px !important; }
            .uwi-appels-toolbar-row {
              flex-direction: column !important;
              align-items: stretch !important;
              gap: 10px !important;
              padding: 12px 14px !important;
            }
            .uwi-appels-toolbar-row > span { text-align: center; }
          }
        `}
      </style>
      <div style={{ minHeight: "100%" }}>
        <main className="uwi-appels-main" style={{ flex: 1, minWidth: 0, padding: "28px 32px" }}>
          <header
            className="uwi-appels-page-header"
            style={{
              display: "flex",
              flexDirection: compactHeader ? "column" : "row",
              justifyContent: "space-between",
              alignItems: compactHeader ? "stretch" : "flex-start",
              marginBottom: 28,
              gap: 24,
            }}
          >
            <div>
              <h1 style={{ margin: 0, fontSize: 30, fontWeight: 800, letterSpacing: "-0.02em", color: C.navy }}>
                Journal d'appels
              </h1>
              <p style={{ margin: "4px 0 0", fontSize: 14, color: C.muted }}>
                Suivez les appels traités par Clara et les actions à réaliser.
              </p>
            </div>

            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 12,
                width: compactHeader ? "100%" : "auto",
              }}
            >
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 10,
                  height: 44,
                  width: compactHeader ? "100%" : 360,
                  borderRadius: 12,
                  border: `1.5px solid ${searchFocused ? C.teal : C.line}`,
                  background: C.white,
                  padding: "0 16px",
                  transition: "border-color 0.15s ease",
                }}
              >
                <Search size={16} color={C.subtle} style={{ flexShrink: 0 }} />
                <input
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  onFocus={() => setSearchFocused(true)}
                  onBlur={() => setSearchFocused(false)}
                  placeholder="Rechercher un patient, un numéro..."
                  style={{
                    flex: 1,
                    border: "none",
                    outline: "none",
                    background: "transparent",
                    fontSize: 14,
                    color: C.navy,
                  }}
                />
                {query && (
                  <button
                    type="button"
                    onClick={() => setQuery("")}
                    style={{
                      border: "none",
                      background: "none",
                      cursor: "pointer",
                      color: C.subtle,
                      display: "flex",
                      padding: 0,
                    }}
                  >
                    <X size={14} />
                  </button>
                )}
              </div>
              <Hoverable
                as="button"
                style={{
                  width: 44,
                  height: 44,
                  borderRadius: 12,
                  border: `1px solid ${C.line}`,
                  background: C.white,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  cursor: "pointer",
                  color: C.muted,
                }}
                hoverStyle={{ background: C.bg }}
              >
                <AlertCircle size={18} />
              </Hoverable>
            </div>
          </header>

          <section
            style={{
              display: "grid",
              gridTemplateColumns: compactHeader ? "1fr" : "repeat(3, 1fr)",
              gap: 16,
              marginBottom: 24,
            }}
          >
            <KpiCard
              icon={Phone}
              value={counts.total}
              label="appels"
              sublabel="30 derniers jours"
              accent={C.teal}
              onClick={() => applyKpiFilter("total")}
              selected={activeTab === "tous" && activeFilterCount === 0}
            />
            <KpiCard
              icon={Calendar}
              value={counts.rdv}
              label="rendez-vous pris"
              sublabel="30 derniers jours"
              accent={C.green}
              onClick={() => applyKpiFilter("rdv")}
              selected={activeTab === "rendez-vous" && subFilters.type === "all"}
            />
            <KpiCard
              icon={PhoneCall}
              value={counts.rappel}
              label="à rappeler"
              sublabel="action nécessaire"
              accent={C.orange}
              onClick={() => applyKpiFilter("rappel")}
              selected={subFilters.type === "a-rappeler"}
            />
          </section>

          {toast ? (
            <div
              style={{
                marginBottom: 14,
                borderRadius: 10,
                border: `1px solid ${C.tealBorder}`,
                background: C.tealSoft,
                color: C.tealDark,
                padding: "10px 14px",
                fontSize: 12,
                fontWeight: 700,
              }}
            >
              {toast}
            </div>
          ) : null}
          {error ? (
            <div
              style={{
                marginBottom: 14,
                borderRadius: 10,
                border: "1px solid #fecaca",
                background: "#fef2f2",
                color: "#b91c1c",
                padding: "10px 14px",
                fontSize: 12,
                fontWeight: 700,
              }}
            >
              {error}
            </div>
          ) : null}

          <section
            style={{
              borderRadius: 16,
              border: `1px solid ${C.line}`,
              background: C.white,
              boxShadow: "0 1px 3px rgba(10,22,40,0.04)",
              overflow: compactHeader ? "visible" : "hidden",
            }}
          >
            <div
              style={{
                display: "flex",
                flexDirection: compactHeader ? "column" : "row",
                justifyContent: "space-between",
                alignItems: compactHeader ? "stretch" : "center",
                borderBottom: `1px solid ${C.line}`,
                padding: compactHeader ? "8px 10px 10px" : "0 20px",
                position: compactHeader ? "sticky" : "static",
                top: compactHeader ? 0 : "auto",
                zIndex: compactHeader ? 12 : "auto",
                background: C.white,
              }}
            >
              <div style={{ position: "relative" }}>
                <div
                  className="uwi-tabs-scroll"
                  style={{
                    display: "flex",
                    overflowX: compactHeader ? "auto" : "visible",
                    WebkitOverflowScrolling: "touch",
                    scrollbarWidth: "none",
                    scrollSnapType: compactHeader ? "x proximity" : "none",
                    scrollBehavior: compactHeader ? "smooth" : "auto",
                  }}
                >
                  {tabsData.map((tab) => {
                    const isActive = activeTab === tab.key;
                    const count = tab.key === "a-traiter" ? counts.toTreat : tab.key === "sans-fiche" ? counts.unknown : null;
                    return (
                      <button
                        key={tab.key}
                        type="button"
                        onClick={() => setActiveTab(tab.key)}
                        style={{
                          position: "relative",
                          display: "flex",
                          alignItems: "center",
                          gap: 6,
                          padding: compactHeader ? "14px 18px" : "14px 16px",
                          minHeight: compactHeader ? 48 : "auto",
                          border: "none",
                          background: "none",
                          cursor: "pointer",
                          fontSize: 13,
                          fontWeight: 700,
                          color: isActive ? C.teal : C.muted,
                          transition: "color 0.15s ease",
                          whiteSpace: "nowrap",
                          scrollSnapAlign: compactHeader ? "start" : "none",
                        }}
                      >
                        {tab.label}
                        {count != null && count > 0 && (
                          <span
                            style={{
                              borderRadius: 99,
                              background: C.orangeSoft,
                              padding: "2px 6px",
                              fontSize: 10,
                              fontWeight: 800,
                              color: C.orange,
                            }}
                          >
                            {count}
                          </span>
                        )}
                        {isActive && (
                          <span
                            style={{
                              position: "absolute",
                              bottom: 0,
                              left: 12,
                              right: 12,
                              height: 2.5,
                              borderRadius: 99,
                              background: C.teal,
                            }}
                          />
                        )}
                      </button>
                    );
                  })}
                </div>
                {compactHeader ? (
                  <div
                    aria-hidden
                    style={{
                      pointerEvents: "none",
                      position: "absolute",
                      top: 0,
                      right: 0,
                      width: 26,
                      height: "100%",
                      background: `linear-gradient(to right, rgba(255,255,255,0), ${C.white})`,
                    }}
                  />
                ) : null}
              </div>

              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 10,
                  padding: compactHeader ? "8px 2px 2px" : "8px 0",
                  flexWrap: compactHeader ? "wrap" : "nowrap",
                }}
              >
                {counts.unknown > 0 && (
                  <button
                    type="button"
                    onClick={() => setActiveTab("sans-fiche")}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 6,
                      border: "none",
                      background: "none",
                      cursor: "pointer",
                      fontSize: compactHeader ? 11 : 12,
                      fontWeight: 700,
                      color: C.orange,
                    }}
                  >
                    <AlertCircle size={14} />
                    {counts.unknown} sans fiche patient
                  </button>
                )}
                <Hoverable
                  as="button"
                  onClick={() => setFilterOpen((prev) => !prev)}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 6,
                    borderRadius: 8,
                    border: `1px solid ${C.line}`,
                    background: C.white,
                    padding: compactHeader ? "10px 12px" : "8px 12px",
                    fontSize: 12,
                    fontWeight: 700,
                    color: C.navy,
                    cursor: "pointer",
                    minHeight: compactHeader ? 40 : "auto",
                  }}
                  hoverStyle={{ background: C.bg }}
                >
                  <Filter size={14} />
                  Filtrer
                  {activeFilterCount > 0 ? (
                    <span
                      style={{
                        borderRadius: 99,
                        background: C.tealSoft,
                        padding: "1px 6px",
                        fontSize: 10,
                        fontWeight: 800,
                        color: C.teal,
                      }}
                    >
                      {activeFilterCount}
                    </span>
                  ) : null}
                  <ChevronDown size={14} />
                </Hoverable>
              </div>
            </div>

            {filterOpen ? (
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: compactFilters ? "1fr" : "repeat(5, minmax(0, 1fr))",
                  gap: 10,
                  padding: "12px 20px",
                  borderBottom: `1px solid ${C.line}`,
                  background: C.surface,
                }}
              >
                <select
                  value={subFilters.status}
                  onChange={(event) => updateSubFilter("status", event.target.value)}
                  style={{
                    borderRadius: 8,
                    border: `1px solid ${C.line}`,
                    padding: "8px 10px",
                    fontSize: 12,
                    color: C.navy,
                    background: C.white,
                  }}
                >
                  <option value="all">Statut: tous</option>
                  <option value="à traiter">Statut: à traiter</option>
                  <option value="manqué">Statut: manqué</option>
                  <option value="traité">Statut: traité</option>
                  <option value="résolu">Statut: résolu</option>
                </select>

                <select
                  value={subFilters.type}
                  onChange={(event) => updateSubFilter("type", event.target.value)}
                  style={{
                    borderRadius: 8,
                    border: `1px solid ${C.line}`,
                    padding: "8px 10px",
                    fontSize: 12,
                    color: C.navy,
                    background: C.white,
                  }}
                >
                  <option value="all">Type: tous</option>
                  <option value="rendez-vous">Rendez-vous</option>
                  <option value="a-rappeler">À rappeler</option>
                  <option value="information">Information</option>
                  <option value="appel-manque">Appel manqué</option>
                  <option value="annulation">Annulation</option>
                  <option value="deplacement">Déplacement</option>
                  <option value="sensible">Sensible</option>
                </select>

                <select
                  value={subFilters.patient}
                  onChange={(event) => updateSubFilter("patient", event.target.value)}
                  style={{
                    borderRadius: 8,
                    border: `1px solid ${C.line}`,
                    padding: "8px 10px",
                    fontSize: 12,
                    color: C.navy,
                    background: C.white,
                  }}
                >
                  <option value="all">Patient: tous</option>
                  <option value="known">Avec fiche</option>
                  <option value="unknown">Sans fiche</option>
                </select>

                <select
                  value={subFilters.period}
                  onChange={(event) => updateSubFilter("period", event.target.value)}
                  style={{
                    borderRadius: 8,
                    border: `1px solid ${C.line}`,
                    padding: "8px 10px",
                    fontSize: 12,
                    color: C.navy,
                    background: C.white,
                  }}
                >
                  <option value="all">Période: tout</option>
                  <option value="today">Aujourd'hui</option>
                  <option value="7d">7 derniers jours</option>
                  <option value="30d">30 derniers jours</option>
                </select>

                <button
                  type="button"
                  onClick={resetFilters}
                  style={{
                    borderRadius: 8,
                    border: `1px solid ${C.line}`,
                    background: C.white,
                    padding: "8px 10px",
                    fontSize: 12,
                    fontWeight: 700,
                    color: C.navy,
                    cursor: "pointer",
                    width: compactFilters ? "100%" : "auto",
                  }}
                >
                  Réinitialiser
                </button>
              </div>
            ) : null}

            <div
              className="uwi-appels-toolbar-row"
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                padding: "16px 20px",
              }}
            >
              <Hoverable
                as="button"
                onClick={() => setActiveTab("a-traiter")}
                style={{
                  display: "flex",
                  alignItems: "center",
                  borderRadius: 12,
                  border: "none",
                  background: C.navy,
                  color: C.white,
                  padding: "10px 20px",
                  fontSize: 14,
                  fontWeight: 700,
                  cursor: "pointer",
                  boxShadow: "0 4px 12px rgba(10,22,40,0.15)",
                }}
                hoverStyle={{ background: C.navyHover }}
              >
                <LayoutList size={16} style={{ marginRight: 10 }} />
                Voir les appels à traiter
                {counts.toTreat > 0 && (
                  <span
                    style={{
                      marginLeft: 10,
                      borderRadius: 99,
                      background: "rgba(255,255,255,0.2)",
                      padding: "2px 8px",
                      fontSize: 11,
                      fontWeight: 800,
                    }}
                  >
                    {counts.toTreat}
                  </span>
                )}
              </Hoverable>
              <span style={{ fontSize: 12, fontWeight: 600, color: C.subtle }}>
                {filteredCalls.length} appel{filteredCalls.length !== 1 ? "s" : ""}
              </span>
              {filteredCalls.length > 0 ? (
                <Hoverable
                  as="button"
                  type="button"
                  onClick={() => exportCallsToCsv(filteredCalls)}
                  style={{
                    marginLeft: "auto",
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 6,
                    border: `1px solid ${C.line}`,
                    borderRadius: 8,
                    background: C.white,
                    padding: "6px 12px",
                    fontSize: 12,
                    fontWeight: 700,
                    color: C.navy,
                    cursor: "pointer",
                  }}
                  hoverStyle={{ background: C.surface }}
                >
                  <FileText size={14} />
                  Exporter (CSV)
                </Hoverable>
              ) : null}
            </div>

            <div
              className="uwi-appels-list-wrap"
              style={{
                margin: "0 20px 20px",
                borderRadius: 12,
                border: `1px solid ${C.line}`,
                overflow: "hidden",
              }}
            >
              {!compactHeader ? (
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "1.4fr 1fr 2.2fr 0.7fr 1.1fr",
                    alignItems: "center",
                    gap: 16,
                    padding: "10px 20px",
                    borderBottom: `1px solid ${C.line}`,
                    background: C.surface,
                    fontSize: 10,
                    fontWeight: 800,
                    textTransform: "uppercase",
                    letterSpacing: "0.08em",
                    color: C.subtle,
                  }}
                >
                  <div>Patient</div>
                  <div>Type</div>
                  <div>Résumé</div>
                  <div style={{ textAlign: "right" }}>Heure</div>
                  <div style={{ textAlign: "right" }}>Action</div>
                </div>
              ) : null}

              {loading ? (
                <div style={{ padding: "24px", fontSize: 13, color: C.muted }}>Chargement des appels...</div>
              ) : (
                groupedCalls.map((group) => {
                  const extra = group.count - 1;
                  const expanded = Boolean(expandedGroups[group.key]);
                  return (
                    <div key={group.lead.id}>
                      <CallRow
                        call={group.lead}
                        selected={selectedCall}
                        onSelect={handleSelect}
                        onPrimaryAction={handlePrimaryAction}
                        compact={compactHeader}
                        groupCount={group.count}
                      />
                      {extra > 0 ? (
                        <>
                          <button
                            type="button"
                            onClick={() => toggleGroup(group.key)}
                            style={{
                              display: "flex",
                              alignItems: "center",
                              gap: 6,
                              width: "100%",
                              padding: "8px 20px",
                              border: "none",
                              borderTop: `1px dashed ${C.line}`,
                              background: C.surface,
                              fontSize: 12,
                              fontWeight: 700,
                              color: C.teal,
                              cursor: "pointer",
                            }}
                          >
                            {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                            {expanded
                              ? "Masquer les autres appels"
                              : `${extra} autre${extra > 1 ? "s" : ""} appel${extra > 1 ? "s" : ""} de ce numéro`}
                          </button>
                          {expanded
                            ? group.items.slice(1).map((c) => (
                                <CallRow
                                  key={c.id}
                                  call={c}
                                  selected={selectedCall}
                                  onSelect={handleSelect}
                                  onPrimaryAction={handlePrimaryAction}
                                  compact={compactHeader}
                                />
                              ))
                            : null}
                        </>
                      ) : null}
                    </div>
                  );
                })
              )}

              {!loading && filteredCalls.length === 0 && (
                <div style={{ padding: "48px 24px", textAlign: "center", fontSize: 14, color: C.muted }}>
                  Aucun appel trouvé.
                </div>
              )}
            </div>

            {!loading && filteredCalls.length > 0 && (
              <Hoverable
                as="button"
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 6,
                  margin: "0 auto 16px",
                  border: "none",
                  borderRadius: 8,
                  background: "none",
                  padding: "8px 16px",
                  fontSize: 14,
                  fontWeight: 700,
                  color: C.muted,
                  cursor: "pointer",
                }}
                hoverStyle={{ background: C.bg, color: C.navy }}
              >
                Afficher plus d'appels
                <ChevronDown size={14} />
              </Hoverable>
            )}
          </section>
        </main>

        <DetailPanel
          call={selectedCall}
          onClose={() => setSelectedCall(null)}
          onCreatePatient={openCreatePatientModal}
          onOpenPatient={(call) => navigate(`/app/patient-dashboard?phone=${encodeURIComponent(call.patient.phone || call.phone || "")}`)}
          onMarkHandled={handleMarkHandled}
          onAddNote={handleAddNote}
          compact={compactHeader}
        />
      </div>

      <CreatePatientFromCallModal
        open={createModalOpen}
        loading={createLoading}
        form={createForm}
        showEmail
        emailRequired
        extendedProfile
        phoneError={createFieldErrors.phoneError}
        emailError={createFieldErrors.emailError}
        birthDateError={createFieldErrors.birthDateError}
        physicianNameError={createFieldErrors.physicianNameError}
        physicianCityError={createFieldErrors.physicianCityError}
        submitDisabled={createSubmitBlocked}
        onChange={(field, value) => setCreateForm((prev) => ({ ...prev, [field]: value }))}
        onClose={() => {
          setCreateModalOpen(false);
          setCreateConflicts([]);
        }}
        onSubmit={handleCreatePatientSubmit}
        subtitleLine={
          <>
            {createConflicts.length ? (
              <PatientDuplicateBanner conflicts={createConflicts} className="mb-3" />
            ) : null}
            <span>
              Source : <strong>appel entrant</strong>
            </span>
          </>
        }
      />
    </div>
  );
}
