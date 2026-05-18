export default function AppTopbar({
  routeMeta,
  isClaraPage,
  claraRulesSummary,
  onOpenNotifications,
  onOpenProfile,
  onOpenMenu,
  notificationsCount = 0,
  styles,
}) {
  const S = styles;
  const isAllConfigured = claraRulesSummary.configured === claraRulesSummary.total;
  return (
    <header className="uwi-topbar" style={S.topbar}>
      <div style={S.topbarLeftSpacer} />
      <div style={S.topbarText}>
        <h1 className="uwi-topbar-title" style={S.topbarTitle}>
          {routeMeta?.title || "UWI"}
        </h1>
        {routeMeta?.sub ? (
          <p className="uwi-topbar-sub" style={S.topbarSub}>
            {routeMeta.sub}
          </p>
        ) : null}
        {isClaraPage ? (
          <div style={S.topbarCounterWrap}>
            <span
              style={{
                ...S.topbarCounter,
                color: isAllConfigured ? "#166534" : "#9A3412",
                background: isAllConfigured ? "#ECFDF3" : "#FFF7ED",
                borderColor: isAllConfigured ? "#BBF7D0" : "#FED7AA",
              }}
            >
              {claraRulesSummary.configured}/{claraRulesSummary.total} règles configurées
            </span>
          </div>
        ) : null}
      </div>

      <div className="uwi-topbar-actions" style={S.topbarActions}>
        <button
          type="button"
          className="uwi-topbar-btn"
          style={{ ...S.iconBtn, position: "relative" }}
          onClick={onOpenNotifications}
          title="Notifications"
          aria-label="Ouvrir les notifications"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M18 16v-5a6 6 0 1 0-12 0v5l-2 2v1h16v-1z" />
            <path d="M10 21a2 2 0 0 0 4 0" />
          </svg>
          {notificationsCount > 0 ? (
            <span
              aria-hidden="true"
              style={{
                position: "absolute",
                top: -4,
                right: -4,
                minWidth: 18,
                height: 18,
                padding: "0 5px",
                borderRadius: 999,
                background: "#EF4444",
                color: "#fff",
                fontSize: 11,
                fontWeight: 800,
                display: "inline-flex",
                alignItems: "center",
                justifyContent: "center",
                border: "2px solid #fff",
              }}
            >
              {notificationsCount > 99 ? "99+" : notificationsCount}
            </span>
          ) : null}
        </button>
        <button
          type="button"
          className="uwi-topbar-btn"
          style={S.dmBtn}
          onClick={onOpenProfile}
          title="Profil"
          aria-label="Ouvrir le profil"
        >
          DM
        </button>
        <button
          type="button"
          className="uwi-burger-btn uwi-topbar-btn"
          style={S.burgerBtn}
          onClick={onOpenMenu}
          title="Menu"
          aria-label="Ouvrir le menu"
        >
          ☰
        </button>
      </div>
    </header>
  );
}
