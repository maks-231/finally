import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Static export: built output lands in frontend/out/ and is served by
  // FastAPI (StaticFiles) in production. See Dockerfile stage 2.
  output: "export",
  images: {
    unoptimized: true,
  },
  // `next dev`'s rewrite proxy (below) gzip-compresses proxied responses
  // whenever the client sends Accept-Encoding: gzip (every real browser).
  // Gzip buffers to build compression blocks, which breaks SSE — the
  // backend already sets Cache-Control: no-cache / X-Accel-Buffering: no,
  // but those are moot once Next re-buffers the stream for compression.
  // No effect on the production static export (no Next.js server runs).
  compress: false,
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
