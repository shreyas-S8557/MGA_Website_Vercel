/**
 * On the live site "How MGA Mentorship Works?" and the "I AM BROKE / I AM
 * PROSPERING" identity content are ONE unified two-column section: a thin
 * dark-navy heading banner (by request — was lavender), then a white body
 * with the copy on the left and
 * the identity illustration on the right. This file used to be split across
 * HowItWorks.tsx + IdentitySection.tsx; it now renders both halves so the
 * DOM/visual structure matches the real page (see IdentitySection.tsx,
 * which is no longer used from app/page.tsx).
 */
export default function HowItWorks() {
  return (
    <section>
      <div className="bg-mga-navy px-6 py-6 text-center">
        <h2 data-reveal="up" className="font-heading text-3xl font-bold text-white sm:text-4xl">
          How MGA Mentorship Works?
        </h2>
      </div>

      <div className="bg-white px-6 py-16">
        {/* The illustration is capped (max-w-sm) so its height roughly
            matches the copy column, and the two are vertically centred on
            each other. The picture sits against the shared centre line,
            right beside the copy it illustrates, instead of drifting to the
            far edge of its column. */}
        <div className="mx-auto grid max-w-5xl items-center gap-10 sm:grid-cols-2 sm:gap-12">
          <div data-reveal="left">
            <h3 className="font-heading text-2xl font-bold leading-snug text-mga-heading sm:text-3xl">
              This isn&rsquo;t just about money - it&rsquo;s about who you
              become
            </h3>
            <p className="mt-4 leading-relaxed text-mga-grayDark">
              Money problems are often symptoms. We dig deep to unearth and
              fix root causes such as identity, accountability and daily
              habits of growth.
            </p>
            <p className="mt-4 leading-relaxed text-mga-grayDark">
              You don&rsquo;t just learn &ldquo;how to budget.&rdquo; You
              become someone who finishes what they start, earns what
              they&rsquo;re worth, and lives on their own terms.
            </p>
            <p className="mt-4 font-semibold text-mga-heading">
              The real product of our MGA Mentorship Program is you, version
              2.0.
            </p>
            <p className="mt-4 leading-relaxed text-mga-grayDark">
              What comes after &ldquo;I am&rdquo; describes your identity.
              That is what we help you transform so you can create new you.
            </p>
          </div>

          {/* Real "I AM BROKE -> I AM PROSPERING" illustration. The labels
              are baked into the artwork itself, so no separate button
              elements are rendered here. */}
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            data-reveal="right"
            data-reveal-delay="150"
            src="/images/broke-prospering.png"
            alt="I AM BROKE transforming into I AM PROSPERING"
            className="mga-illustration mx-auto w-full max-w-sm rounded-lg shadow-md sm:ml-0 sm:justify-self-start"
          />
        </div>
      </div>
    </section>
  );
}
