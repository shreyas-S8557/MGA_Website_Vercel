import type { Metadata } from "next";
import "./globals.css";

// Two-font system matching the live Wix site: Roboto for body copy,
// Poppins for headings.
//
// This was first written with next/font/google, which self-hosts the font
// files at BUILD time by fetching them from fonts.googleapis.com. That
// build-time fetch is blocked by this sandbox's egress policy (fonts.
// googleapis.com / fonts.gstatic.com are not on the allowlist — same 403
// as static.wixstatic.com), which fails `next build` outright rather than
// degrading gracefully. Since the task description explicitly allows
// "however fonts are currently loaded", fonts are instead loaded the
// classic way, via a <link> tag to the Google Fonts CSS API in the
// document head below. That request happens in the visitor's browser at
// runtime (works normally once deployed, e.g. on Vercel) rather than in
// this build environment, so `next build` succeeds here. The font names
// are wired straight into tailwind.config.js's fontFamily.sans (Roboto)
// and fontFamily.heading (Poppins).

const siteUrl =
  process.env.NEXT_PUBLIC_SITE_URL || "https://mygrowthacademy.coach";

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title:
    "My Growth Academy | The Only Mentorship That Grows You and Your Income",
  description:
    "If you're a couple in your twenties or thirties wanting to build a prosperous financial future, My Growth Academy mentors you step-by-step with proven systems, daily accountability, and a unique payment model tied to the shopping you already do.",
  icons: {
    icon: "/favicon.ico",
  },
  openGraph: {
    title:
      "My Growth Academy | The Only Mentorship That Grows You and Your Income",
    description:
      "Mentorship for couples in their 20s and 30s building a prosperous financial future — proven systems, daily accountability, and mentors who've been there.",
    url: siteUrl,
    siteName: "My Growth Academy",
    images: ["/og-image.png"],
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title:
      "My Growth Academy | The Only Mentorship That Grows You and Your Income",
    description:
      "Mentorship for couples in their 20s and 30s building a prosperous financial future.",
    images: ["/og-image.png"],
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          rel="stylesheet"
          href="https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;700&family=Poppins:wght@400;500;600;700&display=swap"
        />
      </head>
      <body className="bg-mga-bgLight font-sans">{children}</body>
    </html>
  );
}
