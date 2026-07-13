import { test, expect } from "./fixtures/auth.js";

test.describe("Admin — Conversion lead en client", () => {
  test("utilise le provisioning complet puis ouvre la fiche tenant", async ({
    loggedInPage: page,
  }) => {
    let createPayload = null;

    await page.route("**/api/admin/leads/lead-e2e", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          id: "lead-e2e",
          cabinet_name: "Cabinet E2E",
          contact_name: "Dr Parcours",
          email: "parcours@example.com",
          callback_phone: "0611223344",
          profession: "Médecin généraliste",
          city: "Lille",
          status: "new",
          notes_log: [],
        }),
      });
    });

    await page.route("**/api/admin/tenants/create", async (route) => {
      createPayload = route.request().postDataJSON();
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          success: true,
          tenant_id: 987,
          idempotent: false,
          results: { tenant_id: 987, warnings: [], errors: [] },
        }),
      });
    });

    await page.route("**/api/admin/tenants/987/params", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ ok: true }),
      });
    });

    await page.goto("/admin/tenants/new?fromLead=lead-e2e");
    await expect(page.getByDisplayValue("Cabinet E2E")).toBeVisible();

    for (let step = 0; step < 7; step += 1) {
      await page.getByRole("button", { name: "Suivant" }).click();
    }
    await page.getByRole("button", { name: "Créer et ouvrir la fiche" }).click();

    await page.waitForURL(/\/admin\/tenants\/987$/, { timeout: 10_000 });
    expect(createPayload).toMatchObject({
      name: "Cabinet E2E",
      email: "parcours@example.com",
      phone: "0611223344",
      sector: "medecin_generaliste",
      plan_key: "growth",
      lead_id: "lead-e2e",
    });
  });
});
