"use client";

import { useState } from "react";

const slides = [
  {
    name: "Charlie & Selma",
    headline: "Found $12,000 a year in hidden cash",
    body: "They discovered $2,000/month in unnecessary spending with just one MGA system: budgeting.",
    image: "/images/charlie-selma.png",
    // Real site: text on the left, illustration on the right.
    imageSide: "right" as const,
  },
  {
    name: "Terry & Nina",
    headline: "From zero to $150K+ invested",
    body: "Terry started on minimum wage with zero savings. Five years later, they’re thriving with over $150,000 invested, and are getting ready to buy a home.",
    image: "/images/terry-nina.png",
    // Real site: text on the left, illustration on the right.
    imageSide: "right" as const,
  },
  {
    name: "Harry",
    headline: "From starter job to a six-figure portfolio",
    body: "Harry followed MGA’s mentorship program to learn how to network to find a job, to find a job, to keep increasing his job income and to grow his investment portfolio from zero to six-figures, and to support his parents financially.",
    image: "/images/harry.png",
    // Real site: this slide reverses the layout — illustration on the left, text on the right.
    imageSide: "left" as const,
  },
];

export default function RealResults() {
  const [index, setIndex] = useState(0);

  const prev = () => setIndex((i) => (i - 1 + slides.length) % slides.length);
  const next = () => setIndex((i) => (i + 1) % slides.length);

  return (
    <section className="bg-mga-bgLight">
      <div className="bg-mga-navy px-6 py-6 text-center">
        <h2 data-reveal="up" className="font-heading text-3xl font-bold text-white sm:text-4xl">
          Real Couples. Real Results.
        </h2>
        <p data-reveal="up" data-reveal-delay="120" className="mt-2 text-white/90">
          You don&rsquo;t need to be perfect or rich to start. These couples
          show what&rsquo;s possible.
        </p>
      </div>

      <div className="mx-auto max-w-5xl px-6 py-16">
        <div data-reveal="up" className="relative mx-auto max-w-4xl">
          <button
            type="button"
            onClick={prev}
            aria-label="Previous result"
            className="absolute -left-4 top-1/2 z-10 hidden -translate-y-1/2 text-4xl text-mga-heading/60 transition hover:-translate-x-1 hover:text-mga-heading sm:-left-12 sm:block"
          >
            &#8249;
          </button>

          {/* Sliding track: all slides sit side by side and the whole
              track translates horizontally, so switching slides glides
              instead of popping to new content. */}
          <div className="overflow-hidden">
            <div
              className="flex transition-transform duration-[600ms] ease-[cubic-bezier(0.22,1,0.36,1)]"
              style={{ transform: `translateX(-${index * 100}%)` }}
            >
              {slides.map((slide, i) => {
                const imgLeft = slide.imageSide === "left";
                return (
                  <div
                    key={slide.name}
                    aria-hidden={i !== index}
                    className={
                      "w-full flex-shrink-0 px-1 " +
                      (i === index ? "mga-slide-active" : "")
                    }
                  >
                    {/* Image and copy sit side by side, vertically centred
                        on each other, and each hugs the shared centre line:
                        when the picture is on the right the copy is
                        left-aligned beside it; when the picture is on the
                        left the copy is right-aligned toward it. */}
                    <div className="grid items-center gap-8 sm:grid-cols-2 sm:gap-12">
                      <div
                        className={
                          "mga-slide-copy order-2 text-left " +
                          (imgLeft ? "sm:order-2 sm:text-right" : "sm:order-1")
                        }
                      >
                        <h3 className="font-heading text-2xl font-bold leading-snug text-mga-heading sm:text-3xl">
                          {slide.name}:
                          <br />
                          {slide.headline}
                        </h3>
                        <div
                          className={
                            "mga-divider mt-4 h-0.5 w-16 bg-mga-heading/60 " +
                            (imgLeft ? "mga-divider-right sm:ml-auto" : "")
                          }
                        />
                        <p className="mt-4 leading-relaxed text-mga-grayDark">
                          {slide.body}
                        </p>
                      </div>

                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img
                        src={slide.image}
                        alt={`${slide.name} case study`}
                        className={
                          "mga-slide-img mga-illustration order-1 mx-auto w-full max-w-sm rounded-lg shadow-md " +
                          (imgLeft
                            ? "sm:order-1 sm:mr-0 sm:justify-self-end"
                            : "sm:order-2 sm:ml-0 sm:justify-self-start")
                        }
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          <button
            type="button"
            onClick={next}
            aria-label="Next result"
            className="absolute -right-4 top-1/2 z-10 hidden -translate-y-1/2 text-4xl text-mga-heading/60 transition hover:translate-x-1 hover:text-mga-heading sm:-right-12 sm:block"
          >
            &#8250;
          </button>
        </div>

        {/* mobile prev/next since the arrows are hidden below sm: */}
        <div className="mt-6 flex justify-center gap-8 sm:hidden">
          <button type="button" onClick={prev} aria-label="Previous result" className="text-2xl text-mga-heading">
            &#8249;
          </button>
          <button type="button" onClick={next} aria-label="Next result" className="text-2xl text-mga-heading">
            &#8250;
          </button>
        </div>

        <div className="mt-8 flex justify-center gap-2">
          {slides.map((s, i) => (
            <button
              key={s.name}
              type="button"
              onClick={() => setIndex(i)}
              aria-label={`Go to slide ${i + 1}`}
              aria-current={i === index}
              className={
                "h-2.5 rounded-full transition-all duration-500 " +
                (i === index ? "w-7 bg-mga-heading" : "w-2.5 bg-mga-heading/30 hover:bg-mga-heading/60")
              }
            />
          ))}
        </div>
      </div>
    </section>
  );
}
