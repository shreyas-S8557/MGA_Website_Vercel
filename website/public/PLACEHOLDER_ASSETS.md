# Asset status

The real illustration assets used on the live site were supplied directly
(extracted from the page) and are now wired in. This project has **zero**
runtime dependency on `static.wixstatic.com` or any other external image
host — every image below is a local file under `public/images/`.

## Now real (no longer placeholders)

- `public/images/charlie-selma.png` — "Charlie & Selma" case-study
  illustration (couple + child at a kitchen table, "OLD BUDGET -24K/YEAR"
  → "NEW BUDGET +12K/YEAR"). Used in `components/RealResults.tsx`.
- `public/images/terry-nina.png` — "Terry & Nina" case-study illustration
  (couple in matching aprons, milestone icon labels). Used in
  `components/RealResults.tsx`.
- `public/images/harry.png` — "Harry" case-study illustration (man on a
  laptop in a cafe, "INVESTOR AT 27" / "6-FIGURE JOB" / "NETWORKING WINS").
  Used in `components/RealResults.tsx`.
- `public/images/broke-prospering.png` — the real "I AM BROKE" → "I AM
  PROSPERING" split illustration, labels baked into the artwork. Used in
  `components/HowItWorks.tsx` (the merged How-It-Works/Identity section).
  This replaces an earlier, incorrect recreation that rendered two flat
  placeholder circles plus separate "I AM BROKE"/"I AM PROSPERING" button
  elements underneath — that duplicated content the real image already
  contains, so those extra elements are gone; only the one real image is
  rendered now.
- `public/images/gratitude.png` — the real gratitude illustration (girl
  journaling by a window, "GRATITUDE ISN'T JUST A FEELING — IT'S A
  STRATEGY" baked into the art). Used in `components/GratitudeSection.tsx`.
- `public/images/journey-illustration.png` — the real "5 steps" composite
  image (woman looking out a window + the baked-in numbered step-title
  graphic), used in full. An earlier pass cropped this down to just the
  artwork, assuming the baked-in titles duplicated the live step copy in
  `components/JourneySteps.tsx` — but real screenshots of the live site
  confirmed it actually displays this exact composite image in full,
  alongside (not instead of) the separate, longer-form step descriptions
  in the `<ol>`. Restored to the uncropped original.

- `public/images/logo.png` — the real "mga color logo.png" wordmark,
  supplied directly by the user. Used in `components/Header.tsx` in place
  of the earlier styled-text + inline-SVG recreation.
- `app/icon.png` / `app/apple-icon.png` — the browser-tab favicon. This is
  a small (22×21), low-resolution screenshot crop the user supplied
  directly and explicitly asked to use despite the resolution, rather than
  the teal-arrow crop generated as a stand-in earlier. It's padded onto a
  square canvas (using its own corner color, so there's no visible seam)
  and exported at 32×32 and 180×180. Next.js's App Router picks these up
  automatically (`app/icon.png` for the browser tab, `app/apple-icon.png`
  for iOS home-screen bookmarks) with no extra wiring. If a higher-
  resolution version of this favicon becomes available later, drop it in
  here to sharpen it up.

## Still placeholder / unresolved

- An Open Graph share image at `/public/og-image.png` (1200x630) — still
  missing.
- Real destination URLs for the 6 footer social icons (Facebook, X,
  Instagram, YouTube, LinkedIn, TikTok) in `components/Footer.tsx` — still
  `REPLACE_ME` placeholders; Wix renders these via client-side JS with
  obfuscated hrefs so they were never captured.

## Header behavior

`components/Header.tsx` is `position: fixed` (not pushed down in normal
document flow) with a translucent, blurred background
(`bg-white/40 backdrop-blur-md`), matching the real site: the section
scrolling underneath shows through it via CSS `backdrop-filter`, so its
apparent color shifts continuously — light over the periwinkle hero, dark
indigo crossing the "Real Couples. Real Results." band, near-white over
the cream case-study section, and so on — with no scroll-position JS
needed. Confirmed by extracting frames from a screen recording of the real
site scrolling and comparing against the same scroll positions here.

## Color palette

The `mga` Tailwind palette (coral `#C84739`, cream `#FFF6EF`, indigo
`#36488F`, grays `#8F8F8F`/`#424242`, band lavender `#CBC9DA`, bg
periwinkle `#969CBD`) was re-checked against the newly supplied real
illustrations and a fresh full HTML scrape of the live site. The four core
brand colors above are confirmed exact hex matches in the scrape and were
left unchanged. A few other hex values appear in the scrape (`#ea492e`,
`#116dff`, `#3899ec`) but on inspection are generic Wix editor/player
chrome (focus rings, hover states on Wix's own UI controls), not this
site's brand colors, so they were intentionally not adopted. See the task
report for the exact pixel samples taken from the illustrations.
