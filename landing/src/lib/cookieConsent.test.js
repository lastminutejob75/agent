import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  STORAGE_KEY,
  getCookieConsent,
  hasConsentDecision,
  setCookieConsent,
} from "./cookieConsent.js";

describe("cookieConsent", () => {
  beforeEach(() => {
    vi.stubGlobal("document", {
      head: { appendChild: vi.fn() },
      createElement: vi.fn(() => ({ async: false, onload: null, src: "" })),
    });
    vi.stubGlobal("window", {
      localStorage: {
        store: {},
        getItem(key) {
          return this.store[key] ?? null;
        },
        setItem(key, value) {
          this.store[key] = String(value);
        },
        removeItem(key) {
          delete this.store[key];
        },
      },
      dispatchEvent: vi.fn(),
      dataLayer: [],
    });
    window.gtag = vi.fn();
    window.__uwiGaLoaded = false;
    window.__uwiMetaLoaded = false;
    document.head.appendChild = vi.fn();
    document.createElement = vi.fn(() => ({ async: false, onload: null }));
  });

  it("returns null when no decision stored", () => {
    expect(getCookieConsent()).toBeNull();
    expect(hasConsentDecision()).toBe(false);
  });

  it("persists refuse choice", () => {
    setCookieConsent(false);
    expect(getCookieConsent()?.analytics).toBe(false);
    expect(hasConsentDecision()).toBe(true);
    expect(window.localStorage.getItem(STORAGE_KEY)).toContain('"analytics":false');
  });

  it("reads stored accept choice", () => {
    window.localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({ analytics: true, decidedAt: "2026-05-30T12:00:00.000Z" }),
    );
    expect(getCookieConsent()?.analytics).toBe(true);
    expect(hasConsentDecision()).toBe(true);
  });
});
