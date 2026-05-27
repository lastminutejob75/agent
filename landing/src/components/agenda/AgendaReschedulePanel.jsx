import { useEffect, useState } from "react";
import { api } from "../../lib/api.js";

function fmtDay(dateStr) {
  const dt = new Date(`${dateStr}T12:00:00`);
  return dt
    .toLocaleDateString("fr-FR", { weekday: "long", day: "numeric", month: "long" })
    .replace(/^./, (c) => c.toUpperCase());
}

function fmtMonth(d) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

export default function AgendaReschedulePanel({ onClose, onReschedule, loading = false }) {
  const [calMonth, setCalMonth] = useState(() => new Date().toISOString().slice(0, 7));
  const [availDates, setAvailDates] = useState({});
  const [loadingDates, setLoadingDates] = useState(false);
  const [pickedDate, setPickedDate] = useState(null);
  const [daySlots, setDaySlots] = useState([]);
  const [loadingDay, setLoadingDay] = useState(false);
  const [confirmSlot, setConfirmSlot] = useState(null);

  useEffect(() => {
    let cancelled = false;
    setLoadingDates(true);
    api
      .tenantGetAgendaAvailableDates(calMonth)
      .then((res) => {
        if (!cancelled) setAvailDates(res?.dates || {});
      })
      .catch(() => {
        if (!cancelled) setAvailDates({});
      })
      .finally(() => {
        if (!cancelled) setLoadingDates(false);
      });
    return () => {
      cancelled = true;
    };
  }, [calMonth]);

  function loadDay(dateStr) {
    setPickedDate(dateStr);
    setConfirmSlot(null);
    setLoadingDay(true);
    api
      .tenantGetAgendaAvailableSlots(`?date=${dateStr}`)
      .then((res) => setDaySlots(res?.slots || []))
      .catch(() => setDaySlots([]))
      .finally(() => setLoadingDay(false));
  }

  const year = Number(calMonth.slice(0, 4));
  const month = Number(calMonth.slice(5, 7)) - 1;
  const firstDay = new Date(year, month, 1);
  const startDow = (firstDay.getDay() + 6) % 7;
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const cells = [];
  for (let i = 0; i < startDow; i++) cells.push(null);
  for (let d = 1; d <= daysInMonth; d++) cells.push(d);
  while (cells.length % 7 !== 0) cells.push(null);

  const todayStr = new Date().toISOString().slice(0, 10);
  const monthLabel = firstDay
    .toLocaleDateString("fr-FR", { month: "long", year: "numeric" })
    .replace(/^./, (c) => c.toUpperCase());

  if (confirmSlot) {
    return (
      <div className="space-y-4">
        <p className="m-0 text-sm leading-7 text-[#475569]">
          Déplacer ce rendez-vous au <strong>{fmtDay(confirmSlot.date)}</strong> à{" "}
          <strong>{confirmSlot.time}</strong> ?
        </p>
        <div className="flex flex-wrap gap-3">
          <button
            type="button"
            disabled={loading}
            onClick={() => onReschedule?.(confirmSlot)}
            className="rounded-xl bg-[#008EA1] px-4 py-2 text-sm font-black text-white hover:bg-[#007E8C] disabled:opacity-60"
          >
            {loading ? "Déplacement…" : "Confirmer le déplacement"}
          </button>
          <button
            type="button"
            disabled={loading}
            onClick={() => setConfirmSlot(null)}
            className="rounded-xl border border-[#B6C3D7] px-4 py-2 text-sm font-black text-[#53647F] hover:bg-[#F8FAFC]"
          >
            Retour
          </button>
          <button
            type="button"
            disabled={loading}
            onClick={onClose}
            className="rounded-xl border border-[#B6C3D7] px-4 py-2 text-sm font-black text-[#53647F] hover:bg-[#F8FAFC]"
          >
            Annuler
          </button>
        </div>
      </div>
    );
  }

  if (pickedDate) {
    return (
      <div className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h3 className="m-0 text-lg font-black text-[#0A1628]">{fmtDay(pickedDate)}</h3>
          <button
            type="button"
            onClick={() => {
              setPickedDate(null);
              setDaySlots([]);
            }}
            className="rounded-xl border border-[#B6C3D7] px-3 py-1.5 text-xs font-black text-[#53647F] hover:bg-[#F8FAFC]"
          >
            ← Calendrier
          </button>
        </div>
        {loadingDay ? (
          <p className="m-0 text-sm font-semibold text-[#61708B]">Chargement des créneaux…</p>
        ) : daySlots.length === 0 ? (
          <p className="m-0 text-sm font-semibold text-[#61708B]">Aucun créneau libre ce jour.</p>
        ) : (
          <div className="flex flex-wrap gap-2">
            {daySlots.map((slot) => (
              <button
                key={slot.slot_id}
                type="button"
                onClick={() => setConfirmSlot(slot)}
                className="rounded-xl border border-[#72CDE0] bg-[#F2FBFC] px-4 py-2 text-sm font-black text-[#008EA1] hover:bg-[#E9FAFC]"
              >
                {slot.time}
              </button>
            ))}
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <button
          type="button"
          onClick={() => {
            setCalMonth(fmtMonth(new Date(year, month - 1, 1)));
            setPickedDate(null);
            setConfirmSlot(null);
          }}
          className="rounded-xl border border-[#B6C3D7] px-3 py-1.5 text-sm font-black text-[#53647F] hover:bg-[#F8FAFC]"
        >
          ‹
        </button>
        <span className="text-sm font-black text-[#0A1628]">{loadingDates ? "…" : monthLabel}</span>
        <button
          type="button"
          onClick={() => {
            setCalMonth(fmtMonth(new Date(year, month + 1, 1)));
            setPickedDate(null);
            setConfirmSlot(null);
          }}
          className="rounded-xl border border-[#B6C3D7] px-3 py-1.5 text-sm font-black text-[#53647F] hover:bg-[#F8FAFC]"
        >
          ›
        </button>
      </div>
      <div className="grid grid-cols-7 gap-1 text-center text-xs font-bold text-[#64748B]">
        {["Lu", "Ma", "Me", "Je", "Ve", "Sa", "Di"].map((d) => (
          <div key={d}>{d}</div>
        ))}
      </div>
      <div className="grid grid-cols-7 gap-1">
        {cells.map((day, i) => {
          if (day === null) return <div key={`e-${i}`} className="h-10" />;
          const dateStr = `${calMonth}-${String(day).padStart(2, "0")}`;
          const free = availDates[dateStr] || 0;
          const isPast = dateStr < todayStr;
          const hasSlots = free > 0 && !isPast;
          return (
            <button
              key={dateStr}
              type="button"
              disabled={!hasSlots}
              onClick={() => hasSlots && loadDay(dateStr)}
              className={`grid h-10 place-items-center rounded-xl text-sm font-black ${
                hasSlots
                  ? "border border-[#72CDE0] bg-[#E9FAFC] text-[#008EA1] hover:bg-[#D4F4F8]"
                  : "border border-transparent text-[#CBD5E1]"
              } ${dateStr === todayStr ? "ring-2 ring-[#008EA1]/30" : ""}`}
            >
              {day}
            </button>
          );
        })}
      </div>
    </div>
  );
}
