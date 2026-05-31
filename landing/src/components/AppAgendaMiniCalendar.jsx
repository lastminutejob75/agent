import { useEffect, useState } from "react";

const BLUE = "#2563eb";
const TEXT = "#111827";
const MUTED = "#6b7280";
const BORDER = "#e5e7eb";
const BG = "#f5f6f8";
const CARD = "#ffffff";

function getDaysInMonth(year, month) {
  return new Date(year, month + 1, 0).getDate();
}

function getFirstWeekday(year, month) {
  const day = new Date(year, month, 1).getDay();
  return day === 0 ? 6 : day - 1;
}

function formatMonthShort(year, month) {
  const text = new Date(year, month, 1).toLocaleDateString("fr-FR", { month: "short", year: "numeric" });
  return text.charAt(0).toUpperCase() + text.slice(1);
}

const S = {
  miniCalendar: {
    borderRadius: 18,
    border: `1px solid ${BORDER}`,
    background: CARD,
    padding: "14px 14px 12px",
  },
  miniCalendarHeader: {
    display: "grid",
    gridTemplateColumns: "32px 1fr 32px",
    alignItems: "center",
    gap: 10,
    marginBottom: 12,
  },
  miniCalendarNav: {
    height: 32,
    borderRadius: 10,
    border: `1px solid ${BORDER}`,
    background: "#fff",
    color: TEXT,
    fontSize: 18,
    lineHeight: 1,
    cursor: "pointer",
  },
  miniCalendarTitle: {
    textAlign: "center",
    fontSize: 13,
    fontWeight: 700,
    color: TEXT,
  },
  miniCalendarWeekdays: {
    display: "grid",
    gridTemplateColumns: "repeat(7, minmax(0, 1fr))",
    gap: 6,
    marginBottom: 8,
  },
  miniCalendarWeekday: {
    textAlign: "center",
    fontSize: 11,
    fontWeight: 700,
    color: MUTED,
  },
  miniCalendarGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(7, minmax(0, 1fr))",
    gap: 6,
  },
  miniCalendarDay: {
    height: 34,
    borderRadius: 10,
    border: "1px solid transparent",
    background: "transparent",
    color: TEXT,
    fontSize: 12,
    fontWeight: 600,
    cursor: "pointer",
  },
  miniCalendarDaySelected: {
    background: BLUE,
    color: "#fff",
    borderColor: BLUE,
    boxShadow: "0 10px 24px rgba(37,99,235,.22)",
  },
  miniCalendarDayToday: {
    background: BG,
    borderColor: BORDER,
  },
  miniCalendarDayWrap: {
    position: "relative",
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    gap: 2,
  },
  miniCalendarDot: {
    width: 5,
    height: 5,
    borderRadius: 999,
    background: BLUE,
  },
};

export default function AppAgendaMiniCalendar({ selectedDate, onSelect, apptCountByDate = {} }) {
  const selected = new Date(`${selectedDate}T12:00:00`);
  const [view, setView] = useState({ y: selected.getFullYear(), m: selected.getMonth() });

  useEffect(() => {
    const next = new Date(`${selectedDate}T12:00:00`);
    if (Number.isNaN(next.getTime())) return;
    setView({ y: next.getFullYear(), m: next.getMonth() });
  }, [selectedDate]);
  const dim = getDaysInMonth(view.y, view.m);
  const first = getFirstWeekday(view.y, view.m);
  const cells = [...Array(first).fill(null), ...Array.from({ length: dim }, (_, index) => index + 1)];
  const today = new Date();

  return (
    <div style={S.miniCalendar}>
      <div style={S.miniCalendarHeader}>
        <button
          type="button"
          onClick={() => setView((prev) => ({ y: prev.m === 0 ? prev.y - 1 : prev.y, m: prev.m === 0 ? 11 : prev.m - 1 }))}
          style={S.miniCalendarNav}
        >
          ‹
        </button>
        <div style={S.miniCalendarTitle}>{formatMonthShort(view.y, view.m)}</div>
        <button
          type="button"
          onClick={() => setView((prev) => ({ y: prev.m === 11 ? prev.y + 1 : prev.y, m: prev.m === 11 ? 0 : prev.m + 1 }))}
          style={S.miniCalendarNav}
        >
          ›
        </button>
      </div>
      <div style={S.miniCalendarWeekdays}>
        {["L", "M", "M", "J", "V", "S", "D"].map((label, index) => (
          <div key={`${label}-${index}`} style={S.miniCalendarWeekday}>{label}</div>
        ))}
      </div>
      <div style={S.miniCalendarGrid}>
        {cells.map((day, index) => {
          if (!day) return <div key={`empty-${index}`} />;
          const date = new Date(view.y, view.m, day, 12, 0, 0);
          const iso = date.toISOString().slice(0, 10);
          const isSelected = iso === selectedDate;
          const isToday =
            date.getDate() === today.getDate() &&
            date.getMonth() === today.getMonth() &&
            date.getFullYear() === today.getFullYear();
          const apptCount = Number(apptCountByDate[iso] || 0);
          return (
            <div key={iso} style={S.miniCalendarDayWrap}>
              <button
                type="button"
                onClick={() => onSelect(iso)}
                style={{
                  ...S.miniCalendarDay,
                  width: "100%",
                  ...(isSelected ? S.miniCalendarDaySelected : null),
                  ...(isToday && !isSelected ? S.miniCalendarDayToday : null),
                }}
              >
                {day}
              </button>
              {apptCount > 0 ? <span style={S.miniCalendarDot} aria-hidden="true" /> : null}
            </div>
          );
        })}
      </div>
    </div>
  );
}
