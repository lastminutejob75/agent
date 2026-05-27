// Smoke test : dashboard admin charge correctement avec le dataset demo.
import { test, expect } from "./fixtures/auth.js";

test.describe("Admin dashboard", () => {
  test("le dashboard s'affiche apres login (KPIs, sidebar, banniere demo)", async ({ loggedInPage: page }) => {
    await page.goto("/admin");
    // Sidebar : presence des liens principaux
    await expect(page.getByRole("link", { name: /Dashboard/i }).first()).toBeVisible();
    await expect(page.getByRole("link", { name: /Clients/i }).first()).toBeVisible();
    // Banniere "Mode demo" doit etre visible
    await expect(page.locator("text=/mode\\s*d[ée]mo/i").first()).toBeVisible();
  });

  test("API dashboard-payload renvoie un payload coherent en mode demo", async ({ loggedInPage: page, request }) => {
    const cookies = await page.context().cookies();
    const cookieHeader = cookies.map((c) => `${c.name}=${c.value}`).join("; ");
    const apiBase = process.env.E2E_API_BASE_URL || "http://localhost:8000";
    const res = await request.get(`${apiBase}/api/admin/stats/dashboard-payload`, {
      headers: { cookie: cookieHeader },
    });
    expect(res.ok()).toBeTruthy();
    const data = await res.json();
    // Champs minimums attendus
    expect(data).toHaveProperty("kpis");
    expect(typeof data.kpis).toBe("object");
  });
});
