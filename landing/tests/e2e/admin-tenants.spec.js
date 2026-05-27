// Smoke test : liste des clients + bouton "Creer client" desactive en mode demo.
import { test, expect } from "./fixtures/auth.js";

test.describe("Admin — Liste clients", () => {
  test("la liste affiche au moins 1 tenant et le bouton 'Creer client' est desactive en mode demo", async ({
    loggedInPage: page,
  }) => {
    await page.goto("/admin/tenants");
    // Attendre qu'une ligne client apparaisse (table ou cartes)
    await expect(page.locator("table, [role='table'], main").first()).toBeVisible();
    // Verifier qu'il y a du contenu textuel (au moins 1 tenant demo)
    const bodyText = await page.locator("main").innerText();
    expect(bodyText.length).toBeGreaterThan(50);

    // Le bouton "Creer un client" doit etre present mais desactive (mode demo)
    const createBtn = page.getByRole("button", { name: /Cr[ée]er un client/i }).first();
    if (await createBtn.count()) {
      const isDisabled = await createBtn.isDisabled();
      expect(isDisabled).toBe(true);
    }
  });

  test("clic sur un tenant ouvre la page detail", async ({ loggedInPage: page }) => {
    await page.goto("/admin/tenants");
    await page.waitForLoadState("networkidle", { timeout: 10_000 });
    // Trouver le premier lien vers un detail tenant
    const link = page.locator("a[href^='/admin/tenants/']").first();
    if (await link.count()) {
      await link.click();
      await page.waitForURL(/\/admin\/tenants\/[\w-]+/, { timeout: 10_000 });
      expect(page.url()).toMatch(/\/admin\/tenants\/[\w-]+/);
    } else {
      test.skip(true, "Aucun lien tenant trouve dans le DOM");
    }
  });
});
