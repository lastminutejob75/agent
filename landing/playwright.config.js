// Configuration Playwright pour les tests E2E de l'admin UWi.
// Pré-requis :
//   - Backend FastAPI lancé sur :8000 avec ADMIN_DEMO_MODE=true
//   - Frontend Vite lancé sur :3000 (npm run dev)
//
// Lancement :
//   npm run test:e2e         # headless tous les tests
//   npm run test:e2e:ui      # mode UI interactif (recommandé en dev)
//   npm run test:e2e:headed  # voir le navigateur
//
// Variables d'environnement utiles :
//   E2E_BASE_URL          (default http://localhost:3000)
//   E2E_API_BASE_URL      (default http://localhost:8000)
//   E2E_ADMIN_EMAIL       (default admin@uwiapp.com)
//   E2E_ADMIN_PASSWORD    (default adminuwi123)

import { defineConfig, devices } from "@playwright/test";

const BASE_URL = process.env.E2E_BASE_URL || "http://localhost:3000";

export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 30_000,
  expect: { timeout: 7_000 },
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: BASE_URL,
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  // Pas de webServer auto : on suppose que le user lance backend + frontend
  // manuellement (cf. README e2e). Si besoin, decommenter :
  // webServer: {
  //   command: "npm run dev",
  //   url: BASE_URL,
  //   reuseExistingServer: !process.env.CI,
  //   timeout: 60_000,
  // },
});
