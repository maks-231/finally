import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Static export: built output lands in frontend/out/ and is served by
  // FastAPI (StaticFiles) in production. See Dockerfile stage 2.
  output: "export",
  images: {
    unoptimized: true,
  },
  turbopack: {
    root: __dirname,
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
  async rewrites() {
    // Only active in `next dev` — ignored during `next build --output export`.
    // Lets us develop against a locally running backend without CORS.
    return [
      {
        source: "/api/:path*",
        destination: "http://localhost:8000/api/:path*",
      },
    ];
  },
};

export default nextConfig;
