// Real "mga color logo.png" wordmark, supplied directly by the user and
// stored locally at public/images/logo.png — no Wix/CDN runtime dependency.
//
// The real site's header is a translucent, blurred bar fixed to the top of
// the viewport (not pushed down in normal document flow) — the section
// scrolling underneath shows through it, so its apparent color shifts from
// light to dark as you scroll past sections. A `backdrop-blur` +
// semi-transparent background reproduces that exactly (it samples whatever
// pixels are actually behind it) without any scroll listener or per-section
// JS. `position: fixed` (not `sticky`) matches the real site's behavior of
// overlapping the very top of page content rather than reserving its own
// space above it.
//
// The tint is navy (not white): a white/40 overlay over the now-dark-navy
// hero blends to a light periwinkle-blue box that visibly clashes with the
// site's dark-blue-forward palette (confirmed by sampling the rendered
// pixels — white/40 over #36488F comes out ~rgb(134,145,188), noticeably
// lighter/bluer than anything else on the page). A navy-tinted overlay
// still shows the section behind it through and still blurs/lightens on
// scroll, but leans toward the palette instead of away from it.
export default function Header() {
  return (
    <header className="mga-header-in fixed inset-x-0 top-0 z-50 bg-mga-navy/30 px-6 py-4 backdrop-blur-md">
      <div className="mx-auto flex max-w-6xl items-center">
        <a href="#" aria-label="My Growth Academy home">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src="/images/logo.png"
            alt="My Growth Academy"
            className="mga-logo-outline h-12 w-auto sm:h-14"
          />
        </a>
      </div>
    </header>
  );
}
