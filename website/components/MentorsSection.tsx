const beliefs = [
  "Growth Mindset",
  "Entrepreneurship",
  "Power of Mentorship",
];
const beliefsCol2 = [
  "Importance of Right Association",
  "Systems for Driving Right Behaviors, Habits and Identity",
];

/**
 * Real Wix layout has the video/beliefs content and the mentors' story on
 * TWO separate sections with different backgrounds: this one (lavender,
 * the video + "We believe in:" bullet lists) and MentorStorySection.tsx
 * (dark navy, the paragraphs + pull-quote + final CTA). They used to be
 * combined into a single MentorsSection; see MentorStorySection.tsx for the
 * other half.
 */
export default function MentorsSection() {
  return (
    <section className="bg-mga-navy px-6 py-16 text-center">
      <div className="mx-auto max-w-4xl">
        <h2 data-reveal="up" className="font-heading text-3xl font-bold text-mga-bgLight sm:text-4xl">
          Meet the mentors - Kanth &amp; Shaku
        </h2>

        <div data-reveal="zoom" className="mt-8 aspect-video w-full overflow-hidden rounded-lg shadow-md">
          {/* Real YouTube embed — kept exactly, per the migration brief. */}
          <iframe
            className="h-full w-full"
            src="https://www.youtube.com/embed/lQVWl4pGGHw"
            title="Meet the mentors - Kanth & Shaku"
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
            allowFullScreen
          />
        </div>

        <div data-reveal="up" className="mt-10 grid gap-8 text-left sm:grid-cols-2">
          <div>
            <p className="font-semibold text-mga-bgLight">We believe in:</p>
            <ul className="mt-2 list-inside list-disc text-mga-bgLight/90">
              {beliefs.map((b) => (
                <li key={b}>{b}</li>
              ))}
            </ul>
          </div>
          <ul className="mt-2 list-inside list-disc text-mga-bgLight/90 sm:mt-8">
            {beliefsCol2.map((b) => (
              <li key={b}>{b}</li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}
