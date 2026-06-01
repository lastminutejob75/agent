/** Fallback Suspense léger pour les routes lazy (évite flash vide). */
export default function PageRouteSkeleton() {
  return (
    <div
      className="uwi-route-skeleton"
      style={{
        minHeight: "40vh",
        padding: "24px 20px",
        display: "flex",
        flexDirection: "column",
        gap: 12,
      }}
      aria-hidden="true"
    >
      <div
        style={{
          height: 14,
          width: "28%",
          borderRadius: 8,
          background: "linear-gradient(90deg, #eef2f7 25%, #e6ebf2 50%, #eef2f7 75%)",
          backgroundSize: "200% 100%",
          animation: "uwi-route-shimmer 1.2s infinite linear",
        }}
      />
      <div
        style={{
          height: 120,
          borderRadius: 16,
          background: "linear-gradient(90deg, #eef2f7 25%, #e6ebf2 50%, #eef2f7 75%)",
          backgroundSize: "200% 100%",
          animation: "uwi-route-shimmer 1.2s infinite linear",
        }}
      />
      <div
        style={{
          height: 72,
          borderRadius: 16,
          background: "linear-gradient(90deg, #eef2f7 25%, #e6ebf2 50%, #eef2f7 75%)",
          backgroundSize: "200% 100%",
          animation: "uwi-route-shimmer 1.2s infinite linear",
        }}
      />
      <style>{`
        @keyframes uwi-route-shimmer {
          0% { background-position: 200% 0; }
          100% { background-position: -200% 0; }
        }
      `}</style>
    </div>
  );
}
