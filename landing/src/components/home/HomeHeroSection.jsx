export default function HomeHeroSection({
  practitionerName,
  styles,
}) {
  const S = styles;

  return (
    <div className="uwi-dashboard-hero" style={S.hero}>
      <div className="uwi-dashboard-hero-left" style={S.heroLeft}>
        <div>
          <p style={S.heroEyebrow}>
            {new Date().toLocaleDateString("fr-FR", { weekday: "long", day: "numeric", month: "long" })}
          </p>
          <h1 style={S.heroTitle}>Bonjour {practitionerName || "Docteur"}</h1>
          <p style={S.meta}>
            Voici ce qui demande votre attention aujourd&apos;hui.
          </p>
        </div>
      </div>
    </div>
  );
}
