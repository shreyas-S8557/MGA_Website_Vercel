import LeadMagnetModal from "./LeadMagnetModal";

const steps = [
  {
    title: "Step One: Craft Your Future Desired State",
    body: "Fill out a short form writing your financial goals.",
  },
  {
    title: "Step Two: 10-Day Vetting Experience",
    body: "Start actual mentorship: daily growth habits, mindset shifts, early momentum.",
  },
  {
    title: "Step Three: Earn Your Spot",
    body: "Do the work. If you're consistent, you'll get a mentorship offer.",
  },
  {
    title: "Step Four: Begin Long-Term Mentorship",
    body: "Daily check-ins, quarterly one-on-ones, monthly Q&As, on-demand WhatsApp support.",
  },
  {
    title: "Step Five: Compound Your Growth",
    body: "Grow your skills, mindset, and income—slowly, sustainably, for life.",
  },
];

export default function JourneySteps() {
  return (
    <section className="bg-mga-bgLight px-6 py-16">
      <div className="mx-auto max-w-5xl">
        <h2 data-reveal="up" className="text-left font-heading text-3xl font-bold text-mga-heading sm:text-4xl">
          A simple, step-by-step journey that starts growing you right away.
        </h2>

        <div className="mt-10 grid items-center gap-10 sm:grid-cols-2 sm:gap-12">
          {/* Steps text on the LEFT, illustration on the RIGHT (matches the
              live site). */}
          <ol className="space-y-6">
            {steps.map((step, i) => (
              <li
                key={step.title}
                data-reveal="left"
                data-reveal-delay={String(i * 110)}
                className="flex gap-4"
              >
                <span
                  aria-hidden="true"
                  className="mga-step-dot mt-0.5 flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-mga-heading text-sm font-semibold text-white shadow"
                  style={{ animationDelay: `${i * 0.4}s` }}
                >
                  {i + 1}
                </span>
                <div>
                  <p className="font-semibold text-mga-heading">{step.title}</p>
                  <p className="text-mga-grayDark">{step.body}</p>
                </div>
              </li>
            ))}
          </ol>

          {/* Real composite illustration (woman looking out a window +
              the baked-in 5-step title graphic). This was previously
              cropped down to just the artwork on the assumption that the
              baked-in step titles duplicated the live <ol> text to the
              left — but real screenshots of the live site confirm it
              actually shows this FULL composite image as-is, alongside
              the separate, longer-form step copy in the <ol>. Restored to
              the uncropped original to match. */}
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            data-reveal="right"
            data-reveal-delay="150"
            src="/images/journey-illustration.png"
            alt="A woman looking out a window, with the five-step mentorship journey"
            className="mga-illustration mx-auto w-full max-w-md rounded-lg shadow-md sm:ml-0 sm:justify-self-start"
          />
        </div>

        <div data-reveal="up" className="mt-12 text-center">
          <LeadMagnetModal />
        </div>
      </div>
    </section>
  );
}
