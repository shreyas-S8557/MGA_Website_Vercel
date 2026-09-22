/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // Palette re-sampled with PIL directly from the 9 real Wix
        // screenshots (RGB picked at multiple coordinates per section) and
        // cross-checked against hex/rgb literals found in the raw HTML
        // scrape of mygrowthacademy.coach. See website/PLACEHOLDER_ASSETS.md
        // and the task report for the sampled coordinates.
        mga: {
          bg: "#969CBD", // saturated periwinkle, matches the real site exactly, but no longer used on this site by request — the user asked to replace it everywhere with the dark navy below since "light blue doesn't look good"; kept defined in case it's wanted back
          band: "#CBC9DA", // lighter lavender — thin heading-only banner for "How MGA Mentorship Works?" ONLY
          bgLight: "#FFF6EF", // cream — Real Results section bg + modal/lightbox card bg (confirmed exact match in scrape: #FFF6EF)
          navy: "#36488F", // dark navy — now the Hero + mentors/video section bg (swapped in place of the periwinkle `bg` above by request), the mentor-story section bg, AND the "Real Couples. Real Results." heading banner (confirmed exact match in scrape: #36488F)
          heading: "#36488F", // indigo heading text (same value as navy bg, used differently per-section)
          coral: "#C84739", // solid coral CTA button + coral heading text (confirmed exact match in scrape: #C84739)
          accentBlue: "#2A3690", // italic secondary copy (e.g. inside the modal)
          mint: "#63D0A2", // mint-green button INSIDE the modal/lightbox only
          mintDark: "#4FB98D",
          gray: "#8F8F8F", // lighter secondary text (confirmed in scrape)
          grayDark: "#424242", // body paragraph text (confirmed in scrape)
        },
      },
      fontFamily: {
        // Two-font system matching the live site: Roboto for body text,
        // Poppins for headings. Loaded at runtime via the <link> tag in
        // app/layout.tsx (see that file for why — build-time next/font is
        // blocked by this sandbox's egress policy).
        sans: [
          "Roboto",
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "Arial",
          "sans-serif",
        ],
        heading: [
          "Poppins",
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "Arial",
          "sans-serif",
        ],
      },
    },
  },
  plugins: [],
};
