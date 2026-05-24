import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import AdminBillingPage from "./AdminBillingPage.jsx";

const apiMock = vi.hoisted(() => ({
  getBillingSummary: vi.fn(),
  getBillingActionItems: vi.fn(),
  getBillingPlans: vi.fn(),
  listBillingTenants: vi.fn(),
  getBillingTenantOverview: vi.fn(),
  getBillingTenantUsage: vi.fn(),
  getBillingTenantStripe: vi.fn(),
  getBillingTenantInvoices: vi.fn(),
  createStripeCheckout: vi.fn(),
  patchBillingTenantPlan: vi.fn(),
  pushUsageBillingTenant: vi.fn(),
  cancelTenantSubscription: vi.fn(),
  resumeTenantSubscription: vi.fn(),
  getStripePortalLink: vi.fn(),
  syncStripeBilling: vi.fn(),
}));

vi.mock("../../lib/adminApi.js", () => ({
  adminApi: apiMock,
}));

const summaryPayload = {
  period: "2026-05",
  mrr: 447,
  estimated_revenue: 472.2,
  vapi_cost_estimate: 470.92,
  estimated_margin: 1.28,
  estimated_margin_rate: 0.0027,
  voice_minutes_used: 2578,
  estimated_overage_amount: 25.2,
  billing_alerts_count: 6,
};

const actionPayload = {
  items: [
    {
      id: "1:stripe_missing",
      severity: "critical",
      tenant_id: 1,
      tenant_name: "Cabinet Durand",
      title: "Stripe customer manquant",
      description: "Client en onboarding sans abonnement actif.",
    },
  ],
};

const tenantItems = [
  {
    tenant_id: 1,
    name: "Cabinet Lopez",
    plan_key: "pro",
    stripe_status: "active",
    stripe_customer_id: "cus_UWI_lopez",
    stripe_subscription_id: "sub_001",
    current_period_end: 1780272000,
    mrr_eur: 199,
    usage: { minutes: 1368, cost_usd: 246.24 },
    quota: { included: 1200, used: 1368 },
  },
];

const tenantOverview = {
  tenant: {
    tenant_id: 1,
    name: "Cabinet Lopez",
    plan_key: "pro",
    stripe_status: "active",
    stripe_customer_id: "cus_UWI_lopez",
    stripe_subscription_id: "sub_001",
    current_period_end: 1780272000,
    mrr_eur: 199,
    usage: { minutes: 1368, cost_usd: 246.24 },
    quota: { included: 1200, used: 1368 },
    alerts: ["Dépassement minutes"],
  },
};

beforeEach(() => {
  Object.values(apiMock).forEach((fn) => fn.mockReset());
  apiMock.getBillingSummary.mockResolvedValue(summaryPayload);
  apiMock.getBillingActionItems.mockResolvedValue(actionPayload);
  apiMock.getBillingPlans.mockResolvedValue({ items: [{ id: "starter", name: "Starter" }, { id: "growth", name: "Growth" }] });
  apiMock.listBillingTenants.mockResolvedValue({ items: tenantItems, total: 1, page: 1, limit: 300 });
  apiMock.getBillingTenantOverview.mockResolvedValue(tenantOverview);
  apiMock.getBillingTenantUsage.mockResolvedValue({ voice_minutes_used: 1368, included_minutes: 1200 });
  apiMock.getBillingTenantStripe.mockResolvedValue({ stripe_metered_item_id: "si_001", updated_at: "2026-05-18T10:00:00Z" });
  apiMock.getBillingTenantInvoices.mockResolvedValue({ items: [{ id: "inv_1", amount_due: 224.2, status: "paid", number: "INV-001", created: 1780000000 }] });
  apiMock.getStripePortalLink.mockResolvedValue({ url: "https://billing.stripe.com/session/test" });
  apiMock.syncStripeBilling.mockResolvedValue({ items: [] });
  apiMock.pushUsageBillingTenant.mockResolvedValue({ ok: true });
});
afterEach(() => {
  cleanup();
});

function renderWithRoutes(path = "/admin/billing", tenantElement = <AdminBillingPage />) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/admin/billing" element={<AdminBillingPage />} />
        <Route path="/admin/billing/:tenantId" element={tenantElement} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("AdminBillingPage DOM", () => {
  it("affiche la vue plateforme avec KPI + actions + tableau", async () => {
    renderWithRoutes("/admin/billing");

    expect(await screen.findByText("Billing plateforme")).toBeTruthy();
    expect(await screen.findByText("À traiter billing")).toBeTruthy();
    expect(await screen.findByText("Stripe customer manquant")).toBeTruthy();
    expect((await screen.findAllByText("Cabinet Lopez")).length).toBeGreaterThan(0);
  });

  it("ouvre la vue cabinet au clic sur Ouvrir", async () => {
    renderWithRoutes(
      "/admin/billing",
      <div data-testid="billing-tenant-placeholder">Destination cabinet</div>,
    );
    await screen.findByText("Billing plateforme");

    const openBtn = (await screen.findAllByRole("button")).find(
      (b) => String(b.textContent || "").trim() === "Ouvrir",
    );
    expect(openBtn).toBeTruthy();
    fireEvent.click(openBtn);

    expect(await screen.findByTestId("billing-tenant-placeholder")).toBeTruthy();
  });

  it("affiche les données stripe dans l’onglet Stripe cabinet", async () => {
    renderWithRoutes("/admin/billing/1");
    await screen.findByText("Page billing cabinet");

    fireEvent.click(screen.getByRole("button", { name: "Stripe" }));

    await waitFor(() => {
      expect(screen.getByText("Customer ID")).toBeTruthy();
      expect(screen.getByText("cus_UWI_lopez")).toBeTruthy();
    });
  });

  it("applique filtre/tri/recherche et recharge la liste", async () => {
    renderWithRoutes("/admin/billing");
    await screen.findByText("Cabinets billing");

    fireEvent.click(screen.getByRole("button", { name: "Quota élevé" }));
    fireEvent.change(screen.getByDisplayValue("Marge faible"), { target: { value: "mrr" } });
    fireEvent.change(screen.getByPlaceholderText("Rechercher cabinet..."), { target: { value: "Lopez" } });

    await waitFor(() => {
      expect(apiMock.listBillingTenants).toHaveBeenCalledWith(
        expect.objectContaining({
          filter: "quota_high",
          sort: "mrr_desc",
          search: "Lopez",
        }),
      );
    });
  });

  it("déclenche Sync Stripe et gère une erreur API", async () => {
    apiMock.syncStripeBilling.mockRejectedValueOnce(new Error("Erreur 401 — Unauthorized"));
    renderWithRoutes("/admin/billing");
    await screen.findByRole("button", { name: "Sync Stripe" });

    fireEvent.click(screen.getByRole("button", { name: "Sync Stripe" }));

    expect(await screen.findByText("Session admin expirée. Reconnecte-toi pour accéder au billing.")).toBeTruthy();
  });

  it("déclenche Push usage depuis la vue cabinet", async () => {
    renderWithRoutes("/admin/billing/1");
    await screen.findByRole("button", { name: "Pousser usage" });

    fireEvent.click(screen.getByRole("button", { name: "Pousser usage" }));

    await waitFor(() => {
      expect(apiMock.pushUsageBillingTenant).toHaveBeenCalledWith(1);
      expect(screen.getByText("Usage poussé vers Stripe.")).toBeTruthy();
    });
  });
});
