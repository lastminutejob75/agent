export function createLayoutStyles(colors) {
  return {
    adminBanner: {
      position: "fixed",
      top: 0,
      left: 0,
      right: 0,
      zIndex: 80,
      background: "#FFF0F3",
      borderBottom: "1px solid #FECDD3",
      color: "#DC2626",
      padding: "12px 16px",
      fontSize: 13,
      fontWeight: 700,
    },
    brandBtn: {
      border: "none",
      background: "transparent",
      textAlign: "left",
      padding: "20px 18px 14px",
      cursor: "pointer",
    },
    brandName: { fontSize: 38, fontWeight: 900, letterSpacing: "-0.06em", color: colors.title, lineHeight: 1 },
    navBlock: { display: "flex", flexDirection: "column", gap: 4, padding: "8px 10px" },
    sidebarFooter: {
      marginTop: "auto",
      borderTop: `1px solid ${colors.border}`,
      display: "flex",
      alignItems: "center",
      gap: 10,
      padding: "12px 14px",
    },
    avatar: {
      width: 28,
      height: 28,
      borderRadius: "50%",
      background: "linear-gradient(135deg,#009CA4,#14B8A6)",
      color: "#fff",
      display: "grid",
      placeItems: "center",
      fontSize: 10,
      fontWeight: 800,
      flexShrink: 0,
    },
    footerName: { fontSize: 12, fontWeight: 700, color: colors.title, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" },
    footerSub: { fontSize: 10, color: colors.muted },
    logoutButton: {
      border: `1px solid ${colors.border}`,
      background: "#fff",
      width: 26,
      height: 26,
      borderRadius: 8,
      cursor: "pointer",
      color: "#64748B",
      display: "grid",
      placeItems: "center",
      fontSize: 12,
    },
    topbar: {
      position: "static",
      zIndex: 25,
      background: colors.bg,
      borderBottom: `1px solid ${colors.border}`,
      display: "flex",
      alignItems: "center",
      justifyContent: "space-between",
      gap: 14,
      minHeight: 48,
      padding: "8px 24px",
    },
    topbarLeftSpacer: { width: 0, height: 0, display: "none" },
    topbarText: { minWidth: 0, flex: 1 },
    topbarTitle: {
      margin: 0,
      fontSize: 18,
      lineHeight: 1.2,
      letterSpacing: "-0.01em",
      fontWeight: 800,
      color: colors.title,
      whiteSpace: "nowrap",
      overflow: "hidden",
      textOverflow: "ellipsis",
    },
    topbarSub: {
      margin: "2px 0 0",
      fontSize: 12,
      color: colors.text,
      fontWeight: 600,
      whiteSpace: "nowrap",
      overflow: "hidden",
      textOverflow: "ellipsis",
    },
    topbarCounterWrap: { marginTop: 4, display: "flex", alignItems: "center" },
    topbarCounter: {
      fontSize: 11,
      fontWeight: 800,
      borderRadius: 999,
      border: "1px solid",
      padding: "4px 10px",
      display: "inline-flex",
      alignItems: "center",
      justifyContent: "center",
    },
    topbarActions: { display: "flex", alignItems: "center", gap: 10 },
    iconBtn: {
      width: 36,
      height: 36,
      borderRadius: 12,
      border: `1px solid ${colors.border}`,
      background: "#fff",
      cursor: "pointer",
      color: colors.title,
      fontSize: 14,
    },
    helpBtn: {
      borderRadius: 12,
      border: `1px solid ${colors.border}`,
      background: "#fff",
      cursor: "pointer",
      color: colors.title,
      fontSize: 12,
      fontWeight: 700,
      padding: "10px 12px",
    },
    dmBtn: {
      width: 36,
      height: 36,
      borderRadius: 999,
      border: `1px solid ${colors.border}`,
      background: "#fff",
      cursor: "pointer",
      color: colors.title,
      fontSize: 11,
      fontWeight: 800,
    },
    burgerBtn: {
      display: "none",
      width: 36,
      height: 36,
      borderRadius: 12,
      border: `1px solid ${colors.border}`,
      background: "#fff",
      cursor: "pointer",
      color: colors.title,
      fontSize: 16,
    },
    content: { padding: "14px 0 24px", minHeight: "calc(100vh - 96px)" },
    securityBanner: {
      margin: "0 24px 14px",
      borderRadius: 12,
      border: "1px solid #FCD34D",
      background: "#FFFBEB",
      color: "#92400E",
      display: "flex",
      alignItems: "center",
      justifyContent: "space-between",
      flexWrap: "wrap",
      gap: 10,
      padding: "10px 12px",
      fontSize: 13,
      fontWeight: 600,
    },
    primaryBtn: {
      border: "none",
      background: colors.teal,
      color: "#fff",
      borderRadius: 10,
      padding: "9px 12px",
      fontSize: 13,
      fontWeight: 700,
      cursor: "pointer",
    },
    secondaryBtn: {
      border: `1px solid ${colors.border}`,
      background: "#fff",
      color: colors.title,
      borderRadius: 10,
      padding: "9px 12px",
      fontSize: 13,
      fontWeight: 700,
      cursor: "pointer",
    },
  };
}

export function createShellCss(colors) {
  return `
  .uwi-sidebar {
    width: 214px;
    min-width: 214px;
    position: fixed;
    left: 0;
    bottom: 0;
    z-index: 45;
    background: #fff;
    border-right: 1px solid ${colors.border};
    display: flex;
    flex-direction: column;
  }
  .uwi-main {
    margin-left: 214px;
    width: calc(100% - 214px);
    min-height: 100vh;
    display: flex;
    flex-direction: column;
  }
  .uwi-overlay {
    position: fixed;
    inset: 0;
    background: rgba(15, 23, 42, .35);
    z-index: 39;
    opacity: 0;
    pointer-events: none;
    transition: opacity .2s ease;
  }
  .uwi-overlay.open {
    opacity: 1;
    pointer-events: auto;
  }
  .uwi-mobile-nav {
    display: none;
  }
  .uwi-topbar-logout-btn {
    display: none;
  }
  .uwi-shell-item:hover {
    background: #F8FAFC !important;
  }
  @media (max-width: 1024px) {
    .uwi-sidebar {
      display: flex !important;
      width: min(280px, 86vw);
      min-width: 0;
      transform: translateX(-100%);
      transition: transform .2s ease;
      box-shadow: 0 12px 40px rgba(15, 23, 42, 0.18);
    }
    .uwi-sidebar.open {
      transform: translateX(0);
    }
    .uwi-overlay {
      display: block !important;
    }
    .uwi-burger-btn {
      display: inline-grid !important;
    }
    .uwi-topbar-logout-btn {
      display: inline-flex !important;
      align-items: center;
      justify-content: center;
      border-radius: 12px;
      border: 1px solid ${colors.border};
      background: #fff;
      color: #64748B;
      font-size: 11px;
      font-weight: 700;
      padding: 8px 10px;
      cursor: pointer;
      font-family: inherit;
      white-space: nowrap;
    }
    .uwi-main {
      margin-left: 0 !important;
      width: 100% !important;
      padding-bottom: calc(70px + env(safe-area-inset-bottom, 0px));
    }
    .uwi-mobile-nav {
      position: fixed;
      left: 0;
      right: 0;
      bottom: 0;
      z-index: 60;
      display: grid;
      grid-template-columns: repeat(5, minmax(0, 1fr));
      gap: 2px;
      border-top: 1px solid ${colors.border};
      background: rgba(255,255,255,.96);
      padding: 6px 6px max(6px, env(safe-area-inset-bottom, 0px));
      backdrop-filter: blur(8px);
    }
  }
  @media (max-width: 760px) {
    .uwi-topbar {
      min-height: 44px !important;
      padding: 6px 12px !important;
      gap: 8px !important;
    }
    .uwi-topbar-title {
      font-size: 16px !important;
    }
    .uwi-topbar-sub {
      display: none !important;
    }
    .uwi-topbar-actions {
      gap: 6px !important;
    }
    .uwi-topbar-btn {
      width: 32px !important;
      height: 32px !important;
      border-radius: 10px !important;
      font-size: 12px !important;
    }
    .uwi-topbar-help-btn {
      border-radius: 10px !important;
      padding: 8px 9px !important;
      font-size: 11px !important;
    }
    .uwi-topbar-logout-btn {
      display: none !important;
    }
    .uwi-to-process-strip {
      width: calc(100% - 20px) !important;
      margin: 8px 10px 0 !important;
      padding: 10px 12px !important;
      font-size: 13px !important;
    }
  }
`;
}
