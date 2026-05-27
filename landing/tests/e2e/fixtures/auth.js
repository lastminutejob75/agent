// Fixtures Playwright partages : login admin, helpers reseau.
import { test as base, expect } from "@playwright/test";

const ADMIN_EMAIL = process.env.E2E_ADMIN_EMAIL || "admin@uwiapp.com";
const ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD || "adminuwi123";
const API_BASE_URL = process.env.E2E_API_BASE_URL || "http://localhost:8000";

/**
 * Verifie que le backend est en mode demo. Sinon les tests sont skipes
 * pour eviter de toucher a une vraie base.
 */
async function ensureDemoMode(request) {
  const res = await request.get(`${API_BASE_URL}/api/admin/_meta`);
  if (!res.ok()) {
    throw new Error(`Backend injoignable sur ${API_BASE_URL}/api/admin/_meta (status ${res.status()})`);
  }
  const meta = await res.json();
  if (!meta.demo_mode) {
    throw new Error(
      "ADMIN_DEMO_MODE n'est pas active. Lancer le backend avec ADMIN_DEMO_MODE=true pour les tests E2E."
    );
  }
  return meta;
}

/**
 * Realise un login admin via l'UI puis verifie qu'on est bien sur /admin.
 * Reutilisable dans tous les tests via la fixture `loggedInPage`.
 */
async function loginAsAdmin(page) {
  await page.goto("/admin/login");
  await page.getByPlaceholder("admin@cabinet.fr").fill(ADMIN_EMAIL);
  await page.getByPlaceholder("••••••••").fill(ADMIN_PASSWORD);
  await page.getByRole("button", { name: /Se connecter/i }).click();
  await page.waitForURL(/\/admin(?!\/login)/, { timeout: 10_000 });
}

export const test = base.extend({
  // Verifie le mode demo (scope test : depend de `request`)
  demoMeta: async ({ request }, use) => {
    const meta = await ensureDemoMode(request);
    await use(meta);
  },
  // Page deja connectee
  loggedInPage: async ({ page, demoMeta }, use) => {
    void demoMeta;
    await loginAsAdmin(page);
    await use(page);
  },
});

export { expect, ADMIN_EMAIL, ADMIN_PASSWORD, API_BASE_URL };
