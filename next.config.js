/** @type {import('next').NextConfig} */
const nextConfig = {
  // Optimisations pour Vercel
  experimental: {
    serverActions: true,
  },
  // Timeout pour les API routes
  api: {
    responseLimit: false,
  },
}

module.exports = nextConfig
