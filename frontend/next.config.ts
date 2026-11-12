import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

const withNextIntl = createNextIntlPlugin();

const nextConfig: NextConfig = {
  // Self-contained server for the Docker image (frontend/Dockerfile).
  output: "standalone",
  // Lets the dev server be opened as http://127.0.0.1:3000 too (browser automation).
  allowedDevOrigins: ["127.0.0.1"],
};

export default withNextIntl(nextConfig);
