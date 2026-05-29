import React from "react";
import { agendaOriginLabel, agendaSlotDurationMinutes } from "../lib/agendaPatientMeta.js";
import { agendaSlotMotif, formatAgendaSlotHour } from "../lib/agendaSlotParse.js";
function formatBirthDateDisplay(value: unknown) {
  const raw = String(value || "").trim().slice(0, 10);
  if (!raw) return "Non renseignée";
  const d = new Date(`${raw}T12:00:00`);
  if (Number.isNaN(d.getTime())) return raw;
  return d.toLocaleDateString("fr-FR", { day: "numeric", month: "long", year: "numeric" });
}

type StatusBucket = "new" | "active" | "inactive";

export type MobileViewType = "overview" | "appointments" | "history" | "documents";

type DisplayHero = {
  name: string;
  phone: string;
  initials: string;
  gradient: string;
  statusBucket: StatusBucket;
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

type HistoryItem = {
  id: string;
  date_label: string;
  time_label: string;
  type_label: string;
  summary: string;
  status_label: string;
};

function cx(...classes: Array<string | false | null | undefined>) {
  return classes.filter(Boolean).join(" ");
}

function statusMeta(bucket: StatusBucket) {
  if (bucket === "new") return { label: "Nouveau", bg: "#EEF6FF", text: "#1D4ED8", dot: "#3B82F6" };
  if (bucket === "inactive") return { label: "Inactif", bg: "#F1F5F9", text: "#64748B", dot: "#94A3B8" };
  return { label: "Actif", bg: "#EAF8EF", text: "#16A34A", dot: "#16A34A" };
}

function frenchAppointmentDateParts(d: Date) {
  return {
    day: String(d.getDate()),
    monthYear: d.toLocaleDateString("fr-FR", { month: "long", year: "numeric" }),
    dow: d.toLocaleDateString("fr-FR", { weekday: "short" }).replace(".", "").toUpperCase() + ".",
  };
}

function historyIcon(typeLabel: string) {
  const t = typeLabel.toLowerCase();
  if (t.includes("appel")) return "☎";
  if (t.includes("sms")) return "□";
  if (t.includes("note")) return "✎";
  if (t.includes("document")) return "▤";
  if (t.includes("rdv") || t.includes("rendez")) return "▣";
  return "◷";
}

const MOBILE_TABS: Array<{ id: MobileViewType; label: string; icon: string }> = [
  { id: "overview", label: "Aperçu", icon: "⌂" },
  { id: "appointments", label: "RDV", icon: "▣" },
  { id: "history", label: "Historique", icon: "◷" },
  { id: "documents", label: "Documents", icon: "▤" },
];

export type PatientDashboardMobileProps = {
  displayHero: DisplayHero;
  patientCabinetRow: Record<string, unknown> | null;
  patientEmail: string;
  tenantPatientNotFound: boolean;
  activeView: MobileViewType;
  setActiveView: (view: MobileViewType) => void;
  onBackToList: () => void;
  onOpenProfile: () => void;
  onCall: () => void;
  onWhatsApp: () => void;
  onSms: () => void;
  onAddNote: () => void;
  onAddDocument: () => void;
  onOpenHistoryModal: () => void;
  upcomingAppointments: Array<{ slot: Record<string, unknown>; start: Date }>;
  pastAppointments: Array<{ start: Date; key: string }>;
  patientAgendaLoading: boolean;
  apptStatusLabel: (slot: Record<string, unknown>, start: Date) => string;
  renderApptActions: (slot: Record<string, unknown>, start: Date) => React.ReactNode;
  patientNotes: PatientNote[];
  notesLoading: boolean;
  noteDeletingId: number | null;
  onRemoveNote: (id: number) => void;
  patientHistory: HistoryItem[];
  patientHistoryLoading: boolean;
  documents: PatientDocument[];
  documentsLoading: boolean;
  onPreviewDocument: (doc: PatientDocument) => void;
  formatDocDate: (value: string) => string;
};

function MobileTopBar({ onBack }: { onBack: () => void }) {
  return (
    <header className="mb-2.5 flex h-12 items-center justify-between">
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={onBack}
          className="border-none bg-transparent text-[28px] leading-none text-[#007F88]"
          aria-label="Retour à la liste patients"
        >
          ←
        </button>
        <strong className="text-[22px] font-black text-[#0B1628]">Patients</strong>
      </div>
    </header>
  );
}

function MobilePatientHeader({
  displayHero,
  patientEmail,
  patientCabinetRow,
  tenantPatientNotFound,
}: {
  displayHero: DisplayHero;
  patientEmail: string;
  patientCabinetRow: Record<string, unknown> | null;
  tenantPatientNotFound: boolean;
}) {
  const status = statusMeta(displayHero.statusBucket);
  const physician = String(patientCabinetRow?.treating_physician_name || "").trim() || "Non renseigné";

  return (
    <section className="mb-3 rounded-[24px] border border-[#E3EAF2] bg-white p-3.5 shadow-[0_10px_26px_rgba(15,23,42,0.08)]">
      <div className="flex items-center gap-3.5">
        <div
          className={cx(
            "grid h-[82px] w-[82px] shrink-0 place-items-center rounded-[22px] bg-gradient-to-br text-[32px] font-black text-white",
            displayHero.gradient,
          )}
        >
          {displayHero.initials}
        </div>
        <div className="min-w-0 flex-1">
          <h1 className="m-0 break-words text-[28px] font-black leading-[1.05] tracking-[-0.02em] text-[#0B1628]">
            {displayHero.name}
          </h1>
          <span
            className="mt-2 inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-[15px] font-black"
            style={{ backgroundColor: status.bg, color: status.text }}
          >
            <span className="h-2 w-2 rounded-full" style={{ backgroundColor: status.dot }} />
            {status.label}
          </span>
          <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1.5">
            <div className="flex min-w-0 items-center gap-2 text-[15px] font-bold text-[#0B1628] sm:text-lg">
              <HeroSvgIcon name="phone" className="h-4 w-4 shrink-0 text-[#009CA4]" />
              <span className="truncate">{displayHero.phone}</span>
            </div>
            <div className="flex min-w-0 items-center gap-2 text-[14px] font-bold text-[#0B1628] sm:text-[15px]">
              <HeroSvgIcon name="mail" className="h-4 w-4 shrink-0 text-[#009CA4]" />
              <span className="truncate">
                {tenantPatientNotFound
                  ? "Email — créez la fiche"
                  : patientEmail || "Aucun email"}
              </span>
            </div>
          </div>
        </div>
      </div>

      <div className="my-4 h-px bg-[#E3EAF2]" />

      <div className="grid grid-cols-1 gap-2">
        <HeaderInfoRow icon={<HeroSvgIcon name="calendar" className="h-5 w-5" />} label="Naissance">
          {formatBirthDateDisplay(patientCabinetRow?.birth_date)}
        </HeaderInfoRow>
        <HeaderInfoRow icon={<HeroSvgIcon name="user" className="h-5 w-5" />} label="Médecin traitant">
          {physician}
        </HeaderInfoRow>
      </div>
    </section>
  );
}

function HeaderInfoRow({
  icon,
  label,
  children,
}: {
  icon: React.ReactNode;
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex items-center gap-2.5 rounded-2xl border border-[#E3EAF2] bg-[#F8FBFD] px-3 py-2.5">
      <span className="grid w-6 shrink-0 place-items-center text-[#009CA4]">{icon}</span>
      <div className="min-w-0">
        <div className="text-xs font-extrabold uppercase tracking-[0.06em] text-[#8190A6]">{label}</div>
        <div className="mt-0.5 break-words text-[15px] font-extrabold text-[#0B1628]">{children}</div>
      </div>
    </div>
  );
}

function MobileQuickActions({
  onCall,
  onWhatsApp,
  onSms,
  onMore,
}: {
  onCall: () => void;
  onWhatsApp: () => void;
  onSms: () => void;
  onMore: () => void;
}) {
  return (
    <section className="mb-3 grid grid-cols-2 gap-2.5">
      <button
        type="button"
        onClick={onCall}
        className="flex h-[54px] items-center justify-center gap-2 rounded-2xl border border-[#009CA4] bg-[#009CA4] text-base font-black text-white shadow-[0_8px_18px_rgba(15,23,42,0.05)]"
      >
        <HeroSvgIcon name="phone" className="h-4 w-4" />
        Appeler
      </button>
      <button
        type="button"
        onClick={onWhatsApp}
        className="flex h-[54px] items-center justify-center gap-2 rounded-2xl border border-[#E3EAF2] bg-white text-base font-black text-[#0B1628] shadow-[0_8px_18px_rgba(15,23,42,0.05)]"
      >
        <HeroSvgIcon name="whatsapp" className="h-4 w-4" />
        WhatsApp
      </button>
      <button
        type="button"
        onClick={onSms}
        className="flex h-[54px] items-center justify-center gap-2 rounded-2xl border border-[#E3EAF2] bg-white text-base font-black text-[#0B1628] shadow-[0_8px_18px_rgba(15,23,42,0.05)]"
      >
        <HeroSvgIcon name="sms" className="h-4 w-4" />
        SMS
      </button>
      <button
        type="button"
        onClick={onMore}
        className="flex h-[54px] items-center justify-center gap-2 rounded-2xl border border-[#E3EAF2] bg-white text-base font-black text-[#0B1628] shadow-[0_8px_18px_rgba(15,23,42,0.05)]"
      >
        <HeroSvgIcon name="more" className="h-4 w-4" />
        Plus
      </button>
    </section>
  );
}

function MobileContentActions({
  onAddNote,
  onAddDocument,
}: {
  onAddNote: () => void;
  onAddDocument: () => void;
}) {
  return (
    <section className="mb-3 grid grid-cols-2 gap-2.5">
      <button
        type="button"
        onClick={onAddNote}
        className="min-h-[50px] rounded-[15px] border border-[#FDBA74] bg-white text-sm font-black text-[#F97316] shadow-[0_8px_18px_rgba(15,23,42,0.05)]"
      >
        ✎ Ajouter une note
      </button>
      <button
        type="button"
        onClick={onAddDocument}
        className="min-h-[50px] rounded-[15px] border border-[#86EFAC] bg-white text-sm font-black text-[#16A34A] shadow-[0_8px_18px_rgba(15,23,42,0.05)]"
      >
        ▤ Ajouter un document
      </button>
    </section>
  );
}

function MobileTabs({
  active,
  onChange,
}: {
  active: MobileViewType;
  onChange: (view: MobileViewType) => void;
}) {
  return (
    <nav className="sticky top-0 z-10 mb-3 grid grid-cols-4 gap-1.5 rounded-[22px] border border-[#E3EAF2] bg-white p-2 shadow-[0_8px_22px_rgba(15,23,42,0.06)]">
      {MOBILE_TABS.map((tab) => {
        const isActive = active === tab.id;
        return (
          <button
            key={tab.id}
            type="button"
            onClick={() => onChange(tab.id)}
            className={cx(
              "flex flex-col items-center gap-1 rounded-2xl px-1 py-2.5 text-[13px] font-black transition",
              isActive ? "bg-[#EAF8FA] text-[#007F88] shadow-[inset_0_-3px_0_#009CA4]" : "text-[#536175]",
            )}
          >
            <span className="text-[17px] leading-none">{tab.icon}</span>
            {tab.label}
          </button>
        );
      })}
    </nav>
  );
}

function MobileNextAppointment({
  upcoming,
  loading,
  apptStatusLabel,
  renderApptActions,
}: {
  upcoming: Array<{ slot: Record<string, unknown>; start: Date }>;
  loading: boolean;
  apptStatusLabel: (slot: Record<string, unknown>, start: Date) => string;
  renderApptActions: (slot: Record<string, unknown>, start: Date) => React.ReactNode;
}) {
  return (
    <section className="mb-3 rounded-[24px] border border-[#E3EAF2] bg-white p-3.5 shadow-[0_10px_24px_rgba(15,23,42,0.07)]">
      <h2 className="mb-4 text-[21px] font-black text-[#0B1628]">Prochain rendez-vous</h2>
      {loading ? (
        <p className="text-sm font-semibold text-[#61708B]">Chargement de l&apos;agenda…</p>
      ) : upcoming.length === 0 ? (
        <p className="text-sm font-semibold text-[#61708B]">Aucun rendez-vous à venir.</p>
      ) : (
        (() => {
          const { slot, start } = upcoming[0];
          const parts = frenchAppointmentDateParts(start);
          const status = apptStatusLabel(slot, start);
          const statusClass =
            status === "Annulé"
              ? "bg-[#FFF1F1] text-[#B91C1C]"
              : status === "À confirmer"
                ? "bg-[#FFF7ED] text-[#C2410C]"
                : "bg-[#EAF8EF] text-[#16A34A]";
          return (
            <>
              <div className="flex items-start gap-3.5">
                <div className="flex h-[116px] w-[86px] shrink-0 flex-col items-center justify-center rounded-[20px] bg-gradient-to-br from-[#009CA4] to-[#003B63] text-white shadow-[10px_10px_0_rgba(0,156,164,0.08)]">
                  <strong className="text-[34px] leading-none">{parts.day}</strong>
                  <span className="mt-1 text-sm capitalize">{parts.monthYear}</span>
                  <b className="mt-1 text-sm">{parts.dow}</b>
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <strong className="text-[34px] leading-none tracking-[-0.03em]">{formatAgendaSlotHour(start)}</strong>
                    <span className="text-[15px] text-[#465365]">({agendaSlotDurationMinutes(slot)} min)</span>
                    <span className={cx("rounded-xl px-3 py-1.5 text-sm font-black", statusClass)}>{status}</span>
                  </div>
                  <div className="mt-2 grid gap-1 text-sm">
                    <span className="text-[#8190A6]">Motif</span>
                    <strong className="text-[#0B1628]">{agendaSlotMotif(slot) || "Consultation"}</strong>
                    <span className="mt-1 text-[#8190A6]">Origine</span>
                    <strong className="text-[#0B1628]">{agendaOriginLabel(slot)}</strong>
                  </div>
                </div>
              </div>
              <div className="mt-4 [&_.flex-wrap]:grid [&_.flex-wrap]:grid-cols-2 [&_.flex-wrap]:gap-2.5 [&_.flex-wrap]:mt-0 [&_button]:min-h-12 [&_button]:w-full [&_button]:rounded-[14px] [&_button]:text-sm [&_button]:font-black [&_button:nth-child(3)]:col-span-2">
                {renderApptActions(slot, start)}
              </div>
            </>
          );
        })()
      )}
    </section>
  );
}

function MobileContextPatient({
  displayName,
  notes,
  notesLoading,
  noteDeletingId,
  onRemoveNote,
}: {
  displayName: string;
  notes: PatientNote[];
  notesLoading: boolean;
  noteDeletingId: number | null;
  onRemoveNote: (id: number) => void;
}) {
  return (
    <section className="mb-3 rounded-[24px] bg-gradient-to-br from-[#06213E] via-[#003B63] to-[#007B88] p-[18px] text-white shadow-[0_12px_28px_rgba(0,59,99,0.22)]">
      <h2 className="mb-4 text-[22px] font-black">☆ Contexte patient</h2>
      <div className="flex items-center gap-2 text-sm font-black uppercase tracking-[0.08em] text-[#24D0D8]">
        <span className="h-2.5 w-2.5 rounded-full bg-[#24D0D8]" />
        Résumé Clara
      </div>
      <p className="mt-2.5 text-[17px] leading-relaxed text-white/95">
        {displayName} contacte principalement le cabinet par téléphone. Les notes et documents ci-dessous
        permettent à l&apos;équipe de garder le contexte.
      </p>
      <div className="my-4 h-px bg-white/15" />
      <div className="text-[19px] font-black">✎ Notes de l&apos;équipe</div>
      {notesLoading ? (
        <p className="mt-3 text-sm text-white/70">Chargement des notes…</p>
      ) : notes.length === 0 ? (
        <p className="mt-3 text-sm text-white/70">Aucune note pour ce patient.</p>
      ) : (
        <div className="mt-3 space-y-4">
          {notes.slice(0, 3).map((item) => (
            <div key={item.id} className="flex items-end justify-between gap-2.5">
              <div className="min-w-0">
                <p className="m-0 text-base leading-snug">{item.text}</p>
                <span className="text-sm text-white/60">
                  {item.author} · {new Date(item.created_at).toLocaleDateString("fr-FR")}
                </span>
              </div>
              <button
                type="button"
                onClick={() => onRemoveNote(item.id)}
                disabled={noteDeletingId === item.id}
                className="shrink-0 rounded-xl border border-white/45 px-3.5 py-2 text-sm font-extrabold text-white disabled:opacity-50"
              >
                {noteDeletingId === item.id ? "…" : "Supprimer"}
              </button>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function MobileOverviewExtras({
  onOpenProfile,
  onOpenHistoryModal,
}: {
  onOpenProfile: () => void;
  onOpenHistoryModal: () => void;
}) {
  return (
    <>
      <button
        type="button"
        onClick={onOpenProfile}
        className="mb-3 flex w-full items-center justify-between gap-3 rounded-[22px] border border-[#E3EAF2] bg-white p-4 text-left shadow-[0_8px_20px_rgba(15,23,42,0.06)]"
      >
        <div className="flex min-w-0 items-center gap-3.5">
          <div className="grid h-11 w-11 shrink-0 place-items-center rounded-2xl bg-[#EAF8FA] text-xl font-black text-[#007F88]">
            ♙
          </div>
          <div className="min-w-0">
            <div className="text-[17px] font-black text-[#0B1628]">Voir la fiche patient détaillée</div>
            <div className="mt-1 text-[13px] leading-snug text-[#8492A6]">
              Informations médicales, documents et données administratives
            </div>
          </div>
        </div>
        <span className="shrink-0 text-[30px] font-extrabold leading-none text-[#007F88]">›</span>
      </button>

      <section className="mb-3 flex items-center gap-3 rounded-[22px] border border-[#E3EAF2] bg-white p-3.5 shadow-[0_8px_20px_rgba(15,23,42,0.06)]">
        <div className="grid h-11 w-11 shrink-0 place-items-center rounded-2xl border-2 border-[#0B1628] text-[22px]">
          ◷
        </div>
        <div className="min-w-0 flex-1">
          <strong className="block text-base font-black">Historique des rendez-vous</strong>
          <p className="m-0 mt-1 text-[13px] text-[#667085]">Consultez l&apos;ensemble des rendez-vous passés.</p>
        </div>
        <button
          type="button"
          onClick={onOpenHistoryModal}
          className="max-w-[136px] shrink-0 rounded-[14px] border border-[#BFE9EC] bg-white px-3 py-2.5 text-xs font-black text-[#007F88]"
        >
          Voir l&apos;historique complet ›
        </button>
      </section>
    </>
  );
}

function MobileAppointmentsTab({
  upcoming,
  past,
  loading,
  apptStatusLabel,
  renderApptActions,
}: {
  upcoming: Array<{ slot: Record<string, unknown>; start: Date }>;
  past: Array<{ start: Date; key: string }>;
  loading: boolean;
  apptStatusLabel: (slot: Record<string, unknown>, start: Date) => string;
  renderApptActions: (slot: Record<string, unknown>, start: Date) => React.ReactNode;
}) {
  return (
    <>
      <MobileNextAppointment
        upcoming={upcoming}
        loading={loading}
        apptStatusLabel={apptStatusLabel}
        renderApptActions={renderApptActions}
      />
      <section className="mb-3 rounded-[24px] border border-[#E3EAF2] bg-white p-3.5 shadow-[0_10px_24px_rgba(15,23,42,0.07)]">
        <h2 className="mb-2 text-[21px] font-black">Tous les rendez-vous</h2>
        {loading ? (
          <p className="text-sm font-semibold text-[#61708B]">Chargement…</p>
        ) : upcoming.length <= 1 && past.length === 0 ? (
          <p className="text-sm font-semibold text-[#61708B]">Aucun autre rendez-vous.</p>
        ) : (
          <div className="divide-y divide-[#E3EAF2]">
            {upcoming.slice(1).map(({ slot, start }) => {
              const key = `${String(slot.event_id || slot.appointment_id || "")}-${start.toISOString()}`;
              return (
                <div key={key} className="flex gap-3 py-3.5">
                  <div className="flex h-[54px] w-16 shrink-0 items-center justify-center rounded-2xl bg-[#EAF8FA] text-xs font-black text-[#007F88]">
                    {start.toLocaleDateString("fr-FR", { day: "numeric", month: "short" })}
                  </div>
                  <div className="min-w-0 flex-1">
                    <strong className="block text-[#0B1628]">
                      {formatAgendaSlotHour(start)} · {agendaSlotMotif(slot) || "Consultation"}
                    </strong>
                    <p className="m-0 mt-1 text-sm text-[#718096]">
                      {apptStatusLabel(slot, start)} · {agendaOriginLabel(slot)}
                    </p>
                  </div>
                </div>
              );
            })}
            {past.slice(0, 8).map(({ start, key }) => (
              <div key={key} className="flex gap-3 py-3.5">
                <div className="flex h-[54px] w-16 shrink-0 items-center justify-center rounded-2xl bg-[#F1F5F9] text-xs font-black text-[#64748B]">
                  {start.toLocaleDateString("fr-FR", { day: "numeric", month: "short" })}
                </div>
                <div className="min-w-0 flex-1">
                  <strong className="block text-[#0B1628]">
                    {formatAgendaSlotHour(start)} · Consultation
                  </strong>
                  <p className="m-0 mt-1 text-sm text-[#718096]">Terminé</p>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </>
  );
}

function MobileHistoryTab({
  items,
  loading,
}: {
  items: HistoryItem[];
  loading: boolean;
}) {
  return (
    <section className="mb-3 rounded-[24px] border border-[#E3EAF2] bg-white p-3.5 shadow-[0_10px_24px_rgba(15,23,42,0.07)]">
      <h2 className="mb-2 text-[21px] font-black">Historique patient</h2>
      {loading ? (
        <p className="text-sm font-semibold text-[#61708B]">Chargement…</p>
      ) : items.length === 0 ? (
        <p className="text-sm font-semibold text-[#61708B]">Aucune interaction enregistrée.</p>
      ) : (
        <div className="divide-y divide-[#E3EAF2]">
          {items.map((item) => (
            <div key={item.id} className="flex gap-3 py-3.5">
              <div className="grid h-[42px] w-[42px] shrink-0 place-items-center rounded-[14px] bg-[#EAF8FA] text-[#007F88]">
                {historyIcon(item.type_label)}
              </div>
              <div className="min-w-0">
                <strong className="block text-[#0B1628]">{item.type_label}</strong>
                <p className="m-0 mt-1 text-sm text-[#718096]">
                  {item.summary || item.status_label} · {item.date_label}
                  {item.time_label && item.time_label !== "—" ? ` ${item.time_label}` : ""}
                </p>
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function MobileDocumentsTab({
  documents,
  loading,
  onAddDocument,
  onPreviewDocument,
  formatDocDate,
}: {
  documents: PatientDocument[];
  loading: boolean;
  onAddDocument: () => void;
  onPreviewDocument: (doc: PatientDocument) => void;
  formatDocDate: (value: string) => string;
}) {
  return (
    <section className="mb-3 rounded-[24px] border border-[#E3EAF2] bg-white p-3.5 shadow-[0_10px_24px_rgba(15,23,42,0.07)]">
      <h2 className="mb-3 text-[21px] font-black">Documents</h2>
      <button
        type="button"
        onClick={onAddDocument}
        className="mb-3.5 w-full min-h-[50px] rounded-[15px] border border-[#86EFAC] bg-white text-sm font-black text-[#16A34A]"
      >
        ▤ Ajouter un document
      </button>
      {loading ? (
        <p className="text-sm font-semibold text-[#61708B]">Chargement…</p>
      ) : documents.length === 0 ? (
        <p className="text-sm font-semibold text-[#61708B]">Aucun document pour ce patient.</p>
      ) : (
        <div className="divide-y divide-[#E3EAF2]">
          {documents.map((doc) => (
            <div key={doc.id} className="flex items-center justify-between gap-3 py-3.5">
              <div className="min-w-0">
                <strong className="block truncate text-[#0B1628]">{doc.original_name}</strong>
                <p className="m-0 mt-1 text-sm text-[#718096]">
                  Ajouté {doc.created_at ? formatDocDate(doc.created_at) : "récemment"}
                </p>
              </div>
              <button
                type="button"
                onClick={() => onPreviewDocument(doc)}
                className="shrink-0 rounded-[11px] border border-[#E3EAF2] bg-white px-3.5 py-2 text-sm font-extrabold text-[#475569]"
              >
                Voir
              </button>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function HeroSvgIcon({
  name,
  className = "h-5 w-5",
}: {
  name: "phone" | "mail" | "whatsapp" | "sms" | "more" | "calendar" | "user";
  className?: string;
}) {
  const common = className;
  if (name === "phone") {
    return (
      <svg className={common} viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <path d="M8.5 4.5h2.2l1.1 3.2-1.8 1.2a11.5 11.5 0 005.3 5.3l1.2-1.8 3.2 1.1v2.2a1.8 1.8 0 01-1.8 1.8C10.8 17.5 6.5 13.2 6.5 6.3a1.8 1.8 0 011.8-1.8z" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
      </svg>
    );
  }
  if (name === "mail") {
    return (
      <svg className={common} viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <rect x="3.5" y="6" width="17" height="12" rx="2.2" stroke="currentColor" strokeWidth="1.8" />
        <path d="M4 8l8 6 8-6" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
      </svg>
    );
  }
  if (name === "whatsapp") {
    return (
      <svg className={common} viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <circle cx="12" cy="12" r="8.5" stroke="currentColor" strokeWidth="1.8" />
        <path d="M9 10.5c.4 2.2 2.1 4 4.3 4.4l1.2-1.2c.2-.2.5-.3.8-.2 1 .3 2 .1 2.8-.5.3-.2.7-.1.9.1l1.1 1.1c.2.2.2.6 0 .8-1 1-2.4 1.5-3.9 1.3-2.6-.4-4.7-2.5-5.1-5.1-.2-1.5.3-2.9 1.3-3.9.2-.2.6-.2.8 0L9 9.7c.1.3 0 .6-.2.8-.6.8-.8 1.8-.5 2.8.1.3.3.5.7.2z" fill="currentColor" />
      </svg>
    );
  }
  if (name === "sms") {
    return (
      <svg className={common} viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <rect x="3.5" y="5" width="17" height="12" rx="2.2" stroke="currentColor" strokeWidth="1.8" />
        <path d="M8 15.5l-2.5 3.5V15.5H8z" fill="currentColor" />
      </svg>
    );
  }
  if (name === "more") {
    return (
      <svg className={common} viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <circle cx="6" cy="12" r="1.6" fill="currentColor" />
        <circle cx="12" cy="12" r="1.6" fill="currentColor" />
        <circle cx="18" cy="12" r="1.6" fill="currentColor" />
      </svg>
    );
  }
  if (name === "user") {
    return (
      <svg className={common} viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <circle cx="12" cy="8" r="3.5" stroke="currentColor" strokeWidth="1.8" />
        <path d="M5.5 19c.8-3 3.4-5 6.5-5s5.7 2 6.5 5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
      </svg>
    );
  }
  return (
    <svg className={common} viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <rect x="4" y="5.5" width="16" height="14" rx="2.2" stroke="currentColor" strokeWidth="1.8" />
      <path d="M8 4v3M16 4v3M4 10h16" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}

export default function PatientDashboardMobile(props: PatientDashboardMobileProps) {
  const {
    displayHero,
    patientCabinetRow,
    patientEmail,
    tenantPatientNotFound,
    activeView,
    setActiveView,
    onBackToList,
    onOpenProfile,
    onCall,
    onWhatsApp,
    onSms,
    onAddNote,
    onAddDocument,
    onOpenHistoryModal,
    upcomingAppointments,
    pastAppointments,
    patientAgendaLoading,
    apptStatusLabel,
    renderApptActions,
    patientNotes,
    notesLoading,
    noteDeletingId,
    onRemoveNote,
    patientHistory,
    patientHistoryLoading,
    documents,
    documentsLoading,
    onPreviewDocument,
    formatDocDate,
  } = props;

  return (
    <div className="xl:hidden">
      <MobileTopBar onBack={onBackToList} />
      <MobilePatientHeader
        displayHero={displayHero}
        patientEmail={patientEmail}
        patientCabinetRow={patientCabinetRow}
        tenantPatientNotFound={tenantPatientNotFound}
      />
      <MobileQuickActions onCall={onCall} onWhatsApp={onWhatsApp} onSms={onSms} onMore={onOpenProfile} />
      <MobileContentActions onAddNote={onAddNote} onAddDocument={onAddDocument} />
      <MobileTabs active={activeView} onChange={setActiveView} />

      {activeView === "overview" ? (
        <>
          <MobileNextAppointment
            upcoming={upcomingAppointments}
            loading={patientAgendaLoading}
            apptStatusLabel={apptStatusLabel}
            renderApptActions={renderApptActions}
          />
          <MobileContextPatient
            displayName={displayHero.name}
            notes={patientNotes}
            notesLoading={notesLoading}
            noteDeletingId={noteDeletingId}
            onRemoveNote={onRemoveNote}
          />
          <MobileOverviewExtras
            onOpenProfile={onOpenProfile}
            onOpenHistoryModal={onOpenHistoryModal}
          />
        </>
      ) : null}

      {activeView === "appointments" ? (
        <MobileAppointmentsTab
          upcoming={upcomingAppointments}
          past={pastAppointments}
          loading={patientAgendaLoading}
          apptStatusLabel={apptStatusLabel}
          renderApptActions={renderApptActions}
        />
      ) : null}

      {activeView === "history" ? (
        <MobileHistoryTab items={patientHistory} loading={patientHistoryLoading} />
      ) : null}

      {activeView === "documents" ? (
        <MobileDocumentsTab
          documents={documents}
          loading={documentsLoading}
          onAddDocument={onAddDocument}
          onPreviewDocument={onPreviewDocument}
          formatDocDate={formatDocDate}
        />
      ) : null}
    </div>
  );
}
