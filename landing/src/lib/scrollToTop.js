/** Remonte la fenêtre en haut (document + body pour compat Safari). */
export function scrollWindowToTop(behavior = "instant") {
  try {
    window.scrollTo({ top: 0, left: 0, behavior });
  } catch {
    window.scrollTo(0, 0);
  }
  if (document.documentElement) document.documentElement.scrollTop = 0;
  if (document.body) document.body.scrollTop = 0;
}

/** Utile après navigation React Router (contenu lazy peint parfois après le 1er tick). */
export function scrollWindowToTopDeferred() {
  scrollWindowToTop();
  const raf1 = window.requestAnimationFrame(() => {
    scrollWindowToTop();
    window.requestAnimationFrame(() => scrollWindowToTop());
  });
  const timer = window.setTimeout(() => scrollWindowToTop(), 120);
  return () => {
    window.cancelAnimationFrame(raf1);
    window.clearTimeout(timer);
  };
}
