export default function GratitudeSection() {
  return (
    <section className="bg-white px-6 py-16">
      <div className="mx-auto grid max-w-5xl items-center gap-10 sm:grid-cols-2 sm:gap-12">
        {/* Image on the LEFT, text on the RIGHT (matches the live site).
            The image is capped so it's about as tall as the copy, pushed
            against the centre line, and the copy is right-aligned toward
            it so the pair reads as one unit. */}
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          data-reveal="left"
          src="/images/gratitude.png"
          alt="Cultivating gratitude: gratitude isn't just a feeling, it's a strategy"
          className="mga-illustration mx-auto w-full max-w-sm rounded-lg shadow-md sm:mr-0 sm:justify-self-end"
        />

        <div data-reveal="right" data-reveal-delay="150" className="text-left sm:text-right">
          <h2 className="font-heading text-2xl font-bold text-mga-heading sm:text-3xl">
            Cultivating Gratitude:
          </h2>
          <p className="mt-1 font-heading text-xl font-bold text-mga-heading">
            It&rsquo;s not just becoming a better version but being happy in
            the journey
          </p>
          <p className="mt-4 leading-relaxed text-mga-grayDark">
            We help you develop a version of you, the &ldquo;I am
            grateful&rdquo; version. Once you learn how to write gratitudes
            consistently about areas in your life that you want to fix to
            get to your future desired state, your attitude towards those
            areas changes.
          </p>
          <p className="mt-4 leading-relaxed text-mga-grayDark">
            You have shifted your habit of looking at what you don&rsquo;t
            want (negative mental attitude) to what you do want (positive
            mental attitude).
          </p>
          <p className="mt-4 leading-relaxed text-mga-grayDark">
            That makes your journey a happy one; one that keeps looking at
            the progress you have made rather than the gap left to reach
            your goal, for example.
          </p>
        </div>
      </div>
    </section>
  );
}
