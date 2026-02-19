export default function InlineAlert({ kind = "info", title, message }) {
  const bg = kind === "error" ? "#fee2e2" : kind === "warn" ? "#fef3c7" : "#e0f2fe";
  const border = kind === "error" ? "#fecaca" : kind === "warn" ? "#fde68a" : "#bae6fd";
  return (
    <div style={{ background: bg, border: `1px solid ${border}`, padding: 12, borderRadius: 10, marginBottom: 10 }}>
      {title && <div style={{ fontWeight: 700, marginBottom: 6 }}>{title}</div>}
      <div>{message}</div>
    </div>
  );
}
