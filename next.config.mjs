/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // The Python function lives in /api and is deployed by Vercel's Python
  // runtime. Next.js must not try to compile it.
  eslint: { ignoreDuringBuilds: false },
  typescript: { ignoreBuildErrors: false },
};

export default nextConfig;
