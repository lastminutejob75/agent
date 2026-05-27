// Smoke test : page publique praticien /p/:slug se charge avec les sections principales.
import { test, expect } from "@playwright/test";

test.describe("Page publique praticien", () => {
  test("la page demo /p/cabinet-dupond-demo charge", async ({ page }) => {
    await page.goto("/p/cabinet-dupond-demo");
    // Le H1 contient le nom du praticien
    await expect(page.locator("h1").first()).toBeVisible({ timeout: 10_000 });
    const h1Text = await page.locator("h1").first().textContent();
    expect(h1Text || "").toMatch(/Cabinet|Praticien|Dr/i);
  });

  test("les sections horaires + infos pratiques sont presentes", async ({ page }) => {
    await page.goto("/p/cabinet-dupond-demo");
    // H2 "Horaires" doit etre present
    await expect(page.getByRole("heading", { name: /Horaires/i })).toBeVisible({
      timeout: 10_000,
    });
    await expect(
      page.getByRole("heading", { name: /Informations pratiques/i })
    ).toBeVisible();
  });

  test("le titre du document est forme correctement", async ({ page }) => {
    await page.goto("/p/cabinet-dupond-demo");
    await expect(page.locator("h1").first()).toBeVisible({ timeout: 10_000 });
    const title = await page.title();
    expect(title.toLowerCase()).toMatch(/rendez-vous|praticien|cabinet/i);
  });
});
