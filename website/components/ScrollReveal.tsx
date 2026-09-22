"use client";

import { useEffect } from "react";

/**
 * Tiny scroll-reveal driver. Any element with a `data-reveal` attribute
 * (values: "up" | "left" | "right" | "zoom" | "fade") starts hidden and
 * animates in the first time it scrolls into view. An optional
 * `data-reveal-delay` (ms) staggers siblings.
 *
 * The hidden state is only applied once this script has run (it adds
 * `reveal-ready` to <html>), so the page stays fully visible with JS off,
 * and globals.css turns everything off under prefers-reduced-motion.
 */
export default function ScrollReveal() {
  useEffect(() => {
    const root = document.documentElement;
    const els = Array.from(
      document.querySelectorAll<HTMLElement>("[data-reveal]")
    );

    els.forEach((el) => {
      const d = el.dataset.revealDelay;
      if (d) el.style.transitionDelay = `${d}ms`;
    });

    if (!("IntersectionObserver" in window)) {
      els.forEach((el) => el.classList.add("is-visible"));
      return;
    }

    root.classList.add("reveal-ready");

    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-visible");
            io.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.15, rootMargin: "0px 0px -8% 0px" }
    );

    els.forEach((el) => io.observe(el));
    return () => io.disconnect();
  }, []);

  return null;
}
