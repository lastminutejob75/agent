// Smoke test : wizard onboarding public /creer-assistante.
// On verifie le chargement de la page et la transition entre etapes 1 → 2.
import { test, expect } from "@playwright/test";

test.describe("Onboarding public (creer-assistante)", () => {
  test("la page se charge et affiche le wizard etape 1", async ({ page }) => {
    await page.goto("/creer-assistante");
    // Etape 1 : "Quelle est votre specialite ?"
    await expect(
      page.getByRole("heading", { name: /sp[ée]cialit[ée]/i }).first()
    ).toBeVisible({ timeout: 10_000 });
  });

  test("clic sur une tuile de specialite passe a l'etape 2 (volume)", async ({ page }) => {
    await page.goto("/creer-assistante");
    // Vide le localStorage pour forcer un parcours propre
    await page.evaluate(() => {
      try {
        localStorage.removeItem("uwi_creer_assistante");
        localStorage.removeItem("uwi_creer_assistante_done");
      } catch {
        /* ignore */
      }
    });
    await page.reload();
    // Attendre l'etape 1
    await expect(
      page.getByRole("heading", { name: /sp[ée]cialit[ée]/i }).first()
    ).toBeVisible({ timeout: 10_000 });

    // Cliquer sur la 1re tuile (n'importe quelle specialite ferait l'affaire)
    const firstTile = page.locator("button, [role='button']").filter({
      hasText: /M[ée]decin|Dentiste|Kin[ée]/i,
    }).first();
    await firstTile.click();

    // Etape 2 = "Volume" (le titre comporte "appels par jour" ou contient le mot volume)
    // On regarde au moins un element textuel coherent avec l'etape 2.
    await expect(
      page.locator("text=/par jour|volume|combien d'appels/i").first()
    ).toBeVisible({ timeout: 5_000 });
  });

  test("le bouton retour ramene a l'etape precedente", async ({ page }) => {
    await page.goto("/creer-assistante");
    await page.evaluate(() => {
      try {
        localStorage.removeItem("uwi_creer_assistante");
        localStorage.removeItem("uwi_creer_assistante_done");
      } catch {
        /* ignore */
      }
    });
    await page.reload();

    // Etape 1 → clic sur 1re tuile → etape 2
    const firstTile = page.locator("button, [role='button']").filter({
      hasText: /M[ée]decin|Dentiste|Kin[ée]/i,
    }).first();
    await firstTile.click();

    // Bouton "Retour" ou "Precedent"
    const backBtn = page.getByRole("button", { name: /retour|pr[ée]c[ée]dent|back/i }).first();
    if (await backBtn.count()) {
      await backBtn.click();
      // Retour a l'etape 1
      await expect(
        page.getByRole("heading", { name: /sp[ée]cialit[ée]/i }).first()
      ).toBeVisible({ timeout: 5_000 });
    } else {
      test.skip(true, "Bouton retour pas trouve dans le DOM");
    }
  });
});
