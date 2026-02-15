const createNextIntlPlugin = require("next-intl/plugin");

const withNextIntl = createNextIntlPlugin("./src/i18n/request.ts");

/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  // Note: NEXT_PUBLIC_* environment variables are automatically inlined at build time
  // by Next.js 9.4+. No need to explicitly define them in the env field.
  // The API URL should be set via NEXT_PUBLIC_API_URL build-arg in Docker.
};

module.exports = withNextIntl(nextConfig);
