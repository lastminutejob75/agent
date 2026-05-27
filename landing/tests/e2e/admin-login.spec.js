// Smoke test : login admin + landing sur le dashboard.
import { test, expect, ADMIN_EMAIL, ADMIN_PASSWORD } from "./fixtures/auth.js";

test.describe("Admin login", () => {
  test("page de login s'affiche avec les champs attendus", async ({ page, demoMeta }) => {
    expect(demoMeta.demo_mode).toBe(true);
    await page.goto("/admin/login");
    await expect(page.getByPlaceholder("admin@exemple.fr")).toBeVisible();
    await expect(page.getByPlaceholder("••••••••")).toBeVisible();
    await expect(page.getByRole("button", { name: /Se connecter/i })).toBeVisible();
  });

  test("login valide redirige vers /admin", async ({ page }) => {
    await page.goto("/admin/login");
    await page.getByPlaceholder("admin@exemple.fr").fill(ADMIN_EMAIL);
    await page.getByPlaceholder("••••••••").fill(ADMIN_PASSWORD);
    await page.getByRole("button", { name: /Se connecter/i }).click();
    await page.waitForURL(/\/admin(?!\/login)/, { timeout: 10_000 });
    expect(page.url()).toMatch(/\/admin/);
    expect(page.url()).not.toMatch(/\/admin\/login/);
  });

  test("login invalide affiche une erreur", async ({ page }) => {
    await page.goto("/admin/login");
    await page.getByPlaceholder("admin@exemple.fr").fill("wrong@uwiapp.com");
    await page.getByPlaceholder("••••••••").fill("wrong-password");
    await page.getByRole("button", { name: /Se connecter/i }).click();
    // Reste sur la page de login, message d'erreur visible
    await expect(page).toHaveURL(/\/admin\/login/);
    await expect(page.locator("text=/identifiants|invalid|erreur/i")).toBeVisible({ timeout: 5_000 });
  });
});
