/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // No remotePatterns: every image is now served locally from /public
  // (see PLACEHOLDER_ASSETS.md) — zero runtime dependency on Wix.
  async redirects() {
    return [
      {
        source: "/:path*",
        has: [{ type: "host", value: "www.mygrowthacademy.coach" }],
        destination: "https://mygrowthacademy.coach/:path*",
        permanent: true,
      },
    ];
  },
};

module.exports = nextConfig;
