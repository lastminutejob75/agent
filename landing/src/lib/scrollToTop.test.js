/**
 * @vitest-environment jsdom
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { scrollWindowToTop } from "./scrollToTop.js";

describe("scrollWindowToTop", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("scrolls window and document roots to top", () => {
    const scrollTo = vi.fn();
    vi.stubGlobal("window", {
      scrollTo,
    });
    document.documentElement.scrollTop = 500;
    document.body.scrollTop = 500;

    scrollWindowToTop();

    expect(scrollTo).toHaveBeenCalledWith({ top: 0, left: 0, behavior: "instant" });
    expect(document.documentElement.scrollTop).toBe(0);
    expect(document.body.scrollTop).toBe(0);
  });
});
