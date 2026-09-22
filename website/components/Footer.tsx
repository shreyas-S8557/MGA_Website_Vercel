// Social icons in the live site's order: Facebook, X, Instagram, YouTube,
// LinkedIn, TikTok — pointing at the real My Growth Academy profiles.
const socialLinks = [
  {
    label: "Facebook",
    color: "#1877F2",
    href: "https://www.facebook.com/mygrowth.academy/",
    path: "M22 12a10 10 0 1 0-11.6 9.9v-7H7.9V12h2.5V9.8c0-2.5 1.5-3.9 3.8-3.9 1.1 0 2.2.2 2.2.2v2.4h-1.2c-1.2 0-1.6.8-1.6 1.6V12h2.8l-.4 2.9h-2.4v7A10 10 0 0 0 22 12Z",
  },
  {
    label: "X",
    color: "#000000",
    href: "https://x.com/mgacademy_01",
    path: "M18.9 3H21l-6.6 7.5L22.3 21h-6.1l-4.8-6.3L5.9 21H3.8l7.1-8.1L2.9 3H9l4.3 5.7L18.9 3Zm-1 16.2h1.2L7.2 4.7H5.9l12 14.5Z",
  },
  {
    label: "Instagram",
    color: "#E1306C",
    href: "https://www.instagram.com/mygrowth.academy/",
    path: "M12 2c2.7 0 3.1 0 4.1.1 1.1.1 1.9.2 2.6.5.7.3 1.3.6 1.9 1.2.6.6 1 1.2 1.2 1.9.3.7.4 1.5.5 2.6.1 1 .1 1.4.1 4.1s0 3.1-.1 4.1c-.1 1.1-.2 1.9-.5 2.6a5.3 5.3 0 0 1-1.2 1.9 5.3 5.3 0 0 1-1.9 1.2c-.7.3-1.5.4-2.6.5-1 .1-1.4.1-4.1.1s-3.1 0-4.1-.1c-1.1-.1-1.9-.2-2.6-.5a5.3 5.3 0 0 1-1.9-1.2 5.3 5.3 0 0 1-1.2-1.9c-.3-.7-.4-1.5-.5-2.6C2 15.1 2 14.7 2 12s0-3.1.1-4.1c.1-1.1.2-1.9.5-2.6.3-.7.6-1.3 1.2-1.9.6-.6 1.2-1 1.9-1.2.7-.3 1.5-.4 2.6-.5C8.9 2 9.3 2 12 2Zm0 1.8c-2.6 0-3 0-4 .1-1 .1-1.6.2-2 .3-.5.2-.9.4-1.2.8-.4.3-.6.7-.8 1.2-.1.4-.3 1-.3 2-.1 1-.1 1.4-.1 4s0 3 .1 4c.1 1 .2 1.6.3 2 .2.5.4.9.8 1.2.3.4.7.6 1.2.8.4.1 1 .3 2 .3 1 .1 1.4.1 4 .1s3 0 4-.1c1-.1 1.6-.2 2-.3.5-.2.9-.4 1.2-.8.4-.3.6-.7.8-1.2.1-.4.3-1 .3-2 .1-1 .1-1.4.1-4s0-3-.1-4c-.1-1-.2-1.6-.3-2a3.1 3.1 0 0 0-.8-1.2 3.1 3.1 0 0 0-1.2-.8c-.4-.1-1-.3-2-.3-1-.1-1.4-.1-4-.1Zm0 3.5a4.7 4.7 0 1 1 0 9.4 4.7 4.7 0 0 1 0-9.4Zm0 1.8a2.9 2.9 0 1 0 0 5.8 2.9 2.9 0 0 0 0-5.8Zm5-2a1.1 1.1 0 1 1-2.2 0 1.1 1.1 0 0 1 2.2 0Z",
  },
  {
    label: "YouTube",
    color: "#FF0000",
    href: "https://www.youtube.com/channel/UCftnOx2THDA2SlgzyWAVPuQ",
    path: "M23 12s0-3.2-.4-4.7a3 3 0 0 0-2.1-2.1C18.9 4.8 12 4.8 12 4.8s-6.9 0-8.5.4A3 3 0 0 0 1.4 7.3C1 8.8 1 12 1 12s0 3.2.4 4.7a3 3 0 0 0 2.1 2.1c1.6.4 8.5.4 8.5.4s6.9 0 8.5-.4a3 3 0 0 0 2.1-2.1C23 15.2 23 12 23 12ZM9.8 15.5V8.5l6.2 3.5-6.2 3.5Z",
  },
  {
    label: "LinkedIn",
    color: "#0A66C2",
    href: "https://www.linkedin.com/company/mygrowth-academy/",
    path: "M4.98 3.5a2.5 2.5 0 1 1 0 5 2.5 2.5 0 0 1 0-5ZM3 9h4v12H3V9Zm7 0h3.8v1.7h.05c.53-1 1.83-2 3.77-2 4.03 0 4.78 2.65 4.78 6.1V21H18v-5.6c0-1.34-.02-3.06-1.87-3.06-1.87 0-2.16 1.46-2.16 2.96V21H10V9Z",
  },
  {
    label: "TikTok",
    color: "#000000",
    href: "https://www.tiktok.com/@mygrowth.academy",
    path: "M16.6 2h-3.2v13.3a2.9 2.9 0 1 1-2.1-2.8v-3.3a6.2 6.2 0 1 0 5.3 6.1V8.6a7.7 7.7 0 0 0 4.4 1.4V6.8a4.4 4.4 0 0 1-4.4-4.4V2Z",
  },
];

export default function Footer() {
  return (
    <footer className="bg-black px-6 py-12 text-center text-white">
      <p
        data-reveal="up"
        className="font-heading text-sm font-semibold uppercase tracking-[0.2em] text-white/70"
      >
        Follow My Growth Academy
      </p>
      <ul className="mx-auto mt-6 flex max-w-4xl flex-wrap items-center justify-center gap-4">
        {socialLinks.map((link, i) => (
          <li key={link.label} data-reveal="up" data-reveal-delay={String(i * 80)}>
            <a
              href={link.href}
              target="_blank"
              rel="noopener noreferrer"
              aria-label={`My Growth Academy on ${link.label}`}
              title={link.label}
              className="mga-social flex h-11 w-11 items-center justify-center rounded-full bg-white/10 text-white/90 hover:bg-white hover:text-[var(--brand)] focus-visible:bg-white focus-visible:text-[var(--brand)] focus-visible:outline-none"
              style={{ "--brand": link.color } as React.CSSProperties}
            >
              <svg viewBox="0 0 24 24" className="h-5 w-5" fill="currentColor" aria-hidden="true">
                <path d={link.path} />
              </svg>
            </a>
          </li>
        ))}
      </ul>
      <p className="mt-8 text-sm text-white/60">
        © {new Date().getFullYear()} by My Growth Academy
      </p>
    </footer>
  );
}
