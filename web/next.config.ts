import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  env: {
    NEXT_PUBLIC_CONTROL_PLANE_URL: process.env.NEXT_PUBLIC_CONTROL_PLANE_URL || "http://localhost:8080",
    NEXT_PUBLIC_GA_ID: process.env.NEXT_PUBLIC_GA_ID || "",
  },
};

export default nextConfig;
