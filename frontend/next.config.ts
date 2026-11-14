import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone", // small runtime image: .next/standalone/server.js
  cacheComponents: true,
  partialPrefetching: true,
  poweredByHeader: false,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
