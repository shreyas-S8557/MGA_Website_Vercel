import LeadMagnetModal from "./LeadMagnetModal";

export default function Hero() {
  return (
    // Cream hero (mga-bgLight, #FFF6EF) with navy heading and dark-gray body
    // copy -- the navy "Real Couples. Real Results." band directly below it
    // then reads as a clear break into the next section.
    <section className="bg-mga-bgLight px-6 pb-20 pt-36 text-center sm:pt-44">
      <div className="mx-auto max-w-4xl">
        <h1 className="mga-hero-in mga-delay-1 font-heading text-4xl font-bold leading-tight text-mga-heading sm:text-5xl">
          The Only Mentorship That Grows You and Your Income
          <br />
          So You Can Stay Until You Win
        </h1>

        <p className="mga-hero-in mga-delay-2 mx-auto mt-6 max-w-2xl text-lg text-mga-grayDark">
          If you&rsquo;re a couple in your twenties or thirties wanting to
          build a prosperous financial future, we&rsquo;ll mentor you
          step-by-step with proven systems, daily accountability, and a
          unique and affordable payment model tied to the shopping you
          already do.
        </p>

        {/* Opens the on-page lead-magnet quiz modal — see
            LeadMagnetModal.tsx. No external redirect. */}
        <div className="mga-hero-in mga-delay-3 mt-10">
          <LeadMagnetModal />
        </div>
      </div>
    </section>
  );
}
