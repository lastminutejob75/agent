export function CopyButton({ value, label = "Copier", className = "" }) {
  if (value == null || value === "") return null;
  const text = String(value);
  return (
    <button
      type="button"
      onClick={() => navigator.clipboard.writeText(text)}
      className={`text-xs px-2 py-1 rounded bg-gray-100 text-gray-600 hover:bg-gray-200 ${className}`}
      title={`Copier : ${text}`}
    >
      {label}
    </button>
  );
}
