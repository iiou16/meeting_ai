import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Ensure Next.js uses this project directory as the tracing root to avoid monorepo warnings.
  outputFileTracingRoot: __dirname,
};

export default nextConfig;
