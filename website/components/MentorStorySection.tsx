import LeadMagnetModal from "./LeadMagnetModal";

/**
 * Separate dark-navy-background section below MentorsSection.tsx: the
 * mentors' story paragraphs, an italic pull-quote, and a final CTA. On the
 * live site this section's heading band reads ".. Power of Mentorship and
 * Identity" (the tail end of a longer banner that starts in the previous
 * section on scroll).
 */
export default function MentorStorySection() {
  return (
    <section className="bg-mga-navy px-6 py-16 text-white">
      <div className="mx-auto max-w-4xl space-y-4 text-left">
        <p data-reveal="up">
          Between the two of us, we have six degrees, healthy computer
          science careers in the past, and a wealth of leadership experience
          in both the corporate world as well as our own businesses. But we
          were struggling to reach our future desired state of financial
          freedom from jobs, plenty of time with family and friends, living
          an abundant life and doing what we want to do, with who we want to
          do it with and make a difference in people&rsquo;s lives. Finding
          mentors and getting mentored changed all of that. For over two
          decades, we have bought our lives back, we got the remote control
          to our happiness firmly in our own grasp.
        </p>
        <p data-reveal="zoom" className="py-2 text-center text-lg font-semibold italic">
          &ldquo;If you&rsquo;re so successful, why are you talking to
          me?&rdquo;
        </p>
        <p data-reveal="up">
          We&rsquo;re paying it forward. We know that, with the right
          guidance, people can learn how to invest effort and grow
          themselves.
        </p>
        <p data-reveal="up">
          We remember being hungry for more. We were running as fast as we
          could and we were standing still. What we were doing was clearly
          not working. We are grateful that our mentors helped us by being
          difference-makers in our lives.
        </p>
        <p data-reveal="up">
          We are passionate about growing people, transforming their
          mindset, and ultimately being the spark that changes their lives.
        </p>

        <div data-reveal="up" className="pt-6 text-center">
          <LeadMagnetModal />
        </div>
      </div>
    </section>
  );
}
