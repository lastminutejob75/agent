export default function ClaraControlTiles({
  tiles,
  styles,
  colors,
  soft,
  borders,
  renderIcon,
  PillComponent,
  BtnComponent,
  tileKeyFromTitle,
  getRuleCompleteness,
  onOpenModule,
}) {
  const S = styles || {};
  const C = colors || {};
  const Pill = PillComponent;
  const Btn = BtnComponent;

  return (
    <div style={S.tileGrid}>
      {tiles.map(([title, icon, tone, desc, cta]) => (
        <section key={title} style={{ ...S.tile, borderTopColor: C[tone] }}>
          <i style={{ background: soft[tone], color: C[tone] }}>{renderIcon(icon)}</i>
          <div>
            <div style={S.tileHead}>
              <h4 style={{ margin: 0, fontSize: 18 }}>{title}</h4>
              <Pill tone={getRuleCompleteness(tileKeyFromTitle(title)).tone}>
                {getRuleCompleteness(tileKeyFromTitle(title)).label}
              </Pill>
            </div>
            <p style={{ margin: "0 0 10px", color: C.muted }}>{desc}</p>
            <Btn
              style={{ color: C[tone], borderColor: borders[tone] }}
              onClick={() => onOpenModule(tileKeyFromTitle(title))}
            >
              {cta}
            </Btn>
          </div>
        </section>
      ))}
    </div>
  );
}
