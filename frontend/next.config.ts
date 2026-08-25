import type { NextConfig } from "next";
import path from "node:path";
import { fileURLToPath } from "node:url";

const backend = process.env.BACKEND_INTERNAL_URL ?? "http://localhost:8000";
const musicSections = ["tracks", "albums", "artists", "genres", "favorites", "playlists", "search", "settings"];
const frontendRoot = path.dirname(fileURLToPath(import.meta.url));

const nextConfig: NextConfig = {
  output: "standalone",
  poweredByHeader: false,
  allowedDevOrigins: ["127.0.0.1"],
  turbopack: {
    root: frontendRoot,
  },
  devIndicators: process.env.MLIB_E2E === "1" ? false : undefined,
  images: {
    remotePatterns: [{ protocol: "https", hostname: "image.tmdb.org", pathname: "/t/p/**" }],
  },
  experimental: {
    // Keep the proxy above the backend's 1024 MB per-file limit so multipart
    // headers do not cause an otherwise valid upload to be truncated.
    proxyClientMaxBodySize: "1025mb",
  },
  async rewrites() {
    return [
      { source: "/api/:path*", destination: `${backend}/api/:path*` },
      { source: "/health", destination: `${backend}/health` },
      ...musicSections.flatMap((section) => [
        { source: `/music/${section}`, destination: `/${section}` },
        { source: `/music/${section}/:path*`, destination: `/${section}/:path*` },
      ]),
    ];
  },
};

export default nextConfig;
