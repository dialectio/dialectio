import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

const withNextIntl = createNextIntlPlugin();

const nextConfig: NextConfig = {
  // Self-contained server for the Docker image (frontend/Dockerfile).
  output: "standalone",
};

export default withNextIntl(nextConfig);
