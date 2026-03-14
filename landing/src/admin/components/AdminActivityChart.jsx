import React, { useMemo, useState } from "react";

const C = {
  surface: "#0F2236",
  border: "#1E3D56",
  accent: "#00E5A0",
  text: "#FFFFFF",
  muted: "#6B90A8",
};

function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max);
}

function buildChartGeometry(data, width, height, padding) {
  const values = data.map((item) => Number(item?.appels ?? 0));
  const maxValue = Math.max(...values, 1);
  const minValue = 0;
  const innerWidth = width - padding.left - padding.right;
  const innerHeight = height - padding.top - padding.bottom;
  const stepX = data.length > 1 ? innerWidth / (data.length - 1) : 0;

  const points = data.map((item, index) => {
    const value = Number(item?.appels ?? 0);
    const ratio = maxValue === minValue ? 1 : (value - minValue) / (maxValue - minValue || 1);
    return {
      ...item,
      value,
      x: padding.left + stepX * index,
      y: padding.top + innerHeight - ratio * innerHeight,
    };
  });

  const linePath = points
    .map((point, index) => `${index === 0 ? "M" : "L"} ${point.x.toFixed(2)} ${point.y.toFixed(2)}`)
    .join(" ");

  const areaPath = points.length
    ? `${linePath} L ${points.at(-1).x.toFixed(2)} ${(height - padding.bottom).toFixed(2)} L ${points[0].x.toFixed(2)} ${(height - padding.bottom).toFixed(2)} Z`
    : "";

  const ticks = Array.from({ length: 4 }, (_, index) => {
    const ratio = index / 3;
    const value = Math.round(maxValue * (1 - ratio));
    return {
      value,
      y: padding.top + innerHeight * ratio,
    };
  });

  return { points, linePath, areaPath, ticks, maxValue };
}

function TooltipCard({ point, position }) {
  return (
    <div
      style={{
        position: "absolute",
        left: position.left,
        top: position.top,
        transform: "translate(-50%, -100%)",
        pointerEvents: "none",
        zIndex: 2,
      }}
    >
      <div
        style={{
          background: C.surface,
          border: `1px solid ${C.border}`,
          borderRadius: 10,
          padding: "8px 14px",
          fontSize: 12,
          color: C.text,
          boxShadow: "0 10px 22px rgba(0,0,0,0.18)",
          whiteSpace: "nowrap",
        }}
      >
        <strong style={{ color: C.accent }}>{point.value}</strong> appels
      </div>
    </div>
  );
}

export default function AdminActivityChart({ data }) {
  const [activeIndex, setActiveIndex] = useState(null);
  const width = 720;
  const height = 160;
  const padding = { top: 10, right: 12, bottom: 22, left: 28 };

  const { points, linePath, areaPath, ticks } = useMemo(
    () => buildChartGeometry(data ?? [], width, height, padding),
    [data],
  );

  const activePoint = activeIndex != null ? points[activeIndex] : null;

  if (!points.length) {
    return <div style={{ height, display: "flex", alignItems: "center", color: C.muted, fontSize: 12 }}>Aucune donnée sur la période.</div>;
  }

  return (
    <div style={{ position: "relative", width: "100%", height }}>
      {activePoint ? (
        <TooltipCard
          point={activePoint}
          position={{
            left: `${clamp((activePoint.x / width) * 100, 10, 90)}%`,
            top: activePoint.y - 10,
          }}
        />
      ) : null}

      <svg viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" style={{ width: "100%", height: "100%", display: "block", overflow: "visible" }}>
        <defs>
          <linearGradient id="admin-activity-gradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={C.accent} stopOpacity="0.28" />
            <stop offset="100%" stopColor={C.accent} stopOpacity="0" />
          </linearGradient>
        </defs>

        {ticks.map((tick) => (
          <g key={`${tick.value}-${tick.y}`}>
            <line
              x1={padding.left}
              x2={width - padding.right}
              y1={tick.y}
              y2={tick.y}
              stroke={C.border}
              strokeOpacity="0.5"
              strokeDasharray="4 4"
            />
            <text x={padding.left - 8} y={tick.y + 4} textAnchor="end" fill={C.muted} fontSize="10">
              {tick.value}
            </text>
          </g>
        ))}

        <path d={areaPath} fill="url(#admin-activity-gradient)" />
        <path d={linePath} fill="none" stroke={C.accent} strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />

        {points.map((point, index) => {
          const isActive = index === activeIndex;
          return (
            <g key={`${point.day}-${index}`}>
              <circle
                cx={point.x}
                cy={point.y}
                r={isActive ? 5 : 3}
                fill={C.accent}
                stroke={C.surface}
                strokeWidth="2"
              />
              <text x={point.x} y={height - 6} textAnchor="middle" fill={C.muted} fontSize="10">
                {point.day}
              </text>
              <rect
                x={point.x - (points.length > 1 ? (points[1].x - points[0].x) / 2 : 24)}
                y={0}
                width={points.length > 1 ? points[1].x - points[0].x : 48}
                height={height}
                fill="transparent"
                onMouseEnter={() => setActiveIndex(index)}
                onMouseLeave={() => setActiveIndex(null)}
              />
            </g>
          );
        })}
      </svg>
    </div>
  );
}
