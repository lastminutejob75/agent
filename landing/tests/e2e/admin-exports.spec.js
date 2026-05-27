// Smoke test : exports CSV depuis le dashboard admin.
import { test, expect, API_BASE_URL } from "./fixtures/auth.js";

test.describe("Admin — Exports CSV", () => {
  test("GET /api/admin/exports/calls.csv renvoie un CSV bien forme", async ({
    loggedInPage: page,
    request,
  }) => {
    const cookies = await page.context().cookies();
    const cookieHeader = cookies.map((c) => `${c.name}=${c.value}`).join("; ");

    const res = await request.get(
      `${API_BASE_URL}/api/admin/exports/calls.csv?days=30&limit=100`,
      { headers: { cookie: cookieHeader } }
    );
    expect(res.ok()).toBeTruthy();
    const ctype = res.headers()["content-type"] || "";
    expect(ctype.toLowerCase()).toContain("text/csv");

    const cd = res.headers()["content-disposition"] || "";
    expect(cd).toMatch(/attachment.*filename/i);

    const body = await res.text();
    // BOM UTF-8 en tete
    expect(body.charCodeAt(0)).toBe(0xfeff);
    // En-tetes attendus
    expect(body).toContain("Date");
    expect(body).toContain("Tenant");
    expect(body).toContain("Resultat");
  });

  test("GET /api/admin/exports/bookings.csv renvoie un CSV bien forme", async ({
    loggedInPage: page,
    request,
  }) => {
    const cookies = await page.context().cookies();
    const cookieHeader = cookies.map((c) => `${c.name}=${c.value}`).join("; ");

    const res = await request.get(
      `${API_BASE_URL}/api/admin/exports/bookings.csv?days=30&limit=100`,
      { headers: { cookie: cookieHeader } }
    );
    expect(res.ok()).toBeTruthy();
    const body = await res.text();
    expect(body.charCodeAt(0)).toBe(0xfeff);
    expect(body).toContain("Patient");
    expect(body).toContain("Telephone");
  });

  test("GET /api/admin/exports/calls.csv sans auth renvoie 401", async ({ request }) => {
    const res = await request.get(
      `${API_BASE_URL}/api/admin/exports/calls.csv?days=7&limit=10`
    );
    expect(res.status()).toBe(401);
  });

  test("le bouton 'Exporter CSV' est visible dans /admin/calls", async ({
    loggedInPage: page,
  }) => {
    await page.goto("/admin/calls");
    await page.waitForLoadState("networkidle", { timeout: 10_000 });
    await expect(
      page.getByRole("button", { name: /exporter csv/i }).first()
    ).toBeVisible({ timeout: 5_000 });
  });
});
