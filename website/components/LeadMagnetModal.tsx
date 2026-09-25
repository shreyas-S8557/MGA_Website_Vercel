"use client";

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";

/**
 * The site's lead magnet: "Your Three-Year Future Snapshot", a short on-page
 * quiz that hands the visitor a personalized Growth Blueprint the moment
 * they finish it — replacing the old flow, which sent every "Craft My
 * Future With AI" click out to an external Google Form (pure lead
 * generation: collect contact info, hand off, visitor sees nothing back).
 *
 * There is no external link-out anywhere in this component. It posts
 * straight to this backend's own POST /api/leads/website (see
 * backend/app/api/mga_leads.py), which profiles the answers, generates a
 * personalized PDF with the existing lead-magnet pipeline, EMAILS it to
 * the visitor, and returns a download link in the same response — so the
 * visitor gets the actual lead magnet in this modal too, not a "thanks,
 * we'll be in touch."
 *
 * The questions below are the real "Three-Year Future Snapshot" questions
 * (the same ones the original Google Form asked), and the `key` on each
 * is written to match backend/app/services/lead_profile_service.py's
 * FIELD_ALIASES exactly (e.g. "three years from now", "biggest thing
 * standing", "realistically commit"), so the existing fuzzy-matching
 * profile step picks every answer up into the right canonical field with
 * no extra field_map plumbing.
 */

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || "https://api.mygrowthacademy.coach";

// Kanth & Shaku's Calendly page -- the "Book a Free Call" button on the
// success screen (the PDF and the email use the same link).
const BOOKING_URL =
  process.env.NEXT_PUBLIC_BOOKING_URL ||
  "https://calendly.com/shaku-c-miriyala/mygrowth-academy";

type Field =
  | {
      type: "text";
      key: string;
      label: string;
      helper?: string;
      optional?: boolean;
    }
  | {
      type: "single";
      key: string;
      label: string;
      options: string[];
    }
  | {
      type: "multi";
      key: string;
      label: string;
      helper?: string;
      options: string[];
      maxSelect?: number;
    }
  | {
      type: "scale";
      key: string;
      label: string;
      lowLabel: string;
      highLabel: string;
      reasonKey: string;
    };

const FIELDS: Field[] = [
  {
    type: "text",
    key: "Where would you like your life to be three years from now?",
    label: "Where would you like your life to be three years from now?",
    helper:
      "Think about your finances, work or business, personal life and relationships, health, and overall lifestyle.",
  },
  {
    type: "text",
    key: "What feels like the biggest thing standing between where you are today and where you want to be?",
    label:
      "What feels like the biggest thing standing between where you are today and where you want to be?",
    helper:
      "For example: lack of clarity, inconsistent habits, limited time, confidence, finances, or not knowing what to focus on first.",
  },
  {
    type: "multi",
    key: "Which areas would you most like to grow in right now?",
    label: "Which areas would you most like to grow in right now?",
    helper: "Choose up to three",
    maxSelect: 3,
    options: [
      "Leadership",
      "Discipline",
      "Confidence",
      "Financial Growth",
      "Time Management",
      "Relationships",
      "Health & Wellness",
      "Business Skills",
      "Other",
    ],
  },
  {
    type: "multi",
    key: "What kind of support do you think would help you make progress faster?",
    label: "What kind of support do you think would help you make progress faster?",
    helper: "Select all that apply",
    options: [
      "Mentorship from people who have already achieved results",
      "A clearer plan or system",
      "Better habits and consistency",
      "New skills or knowledge",
      "A supportive environment or community",
      "I'm not sure yet",
      "Other",
    ],
  },
  {
    type: "single",
    key: "Could you realistically commit 30-45 minutes a day toward improving your habits, skills, and trajectory?",
    label:
      "If the right environment, systems, and mentorship were available to help you grow, could you realistically commit 30–45 minutes a day toward improving your habits, skills, and trajectory?",
    options: ["Yes", "Most days", "A few days a week", "Not right now"],
  },
  {
    type: "scale",
    key: "How serious are you about changing your current trajectory over the next three years?",
    label:
      "How serious are you about changing your current trajectory over the next three years?",
    lowLabel: "Just starting to think about it",
    highLabel: "Ready to make meaningful changes now",
    reasonKey: "What made you choose the above number?",
  },
  {
    type: "single",
    key: "Would you be open to exploring mentorship if we believe we can help?",
    label: "Would you be open to exploring mentorship if we believe we can help?",
    options: ["Yes", "Maybe - I'd like to learn more", "Not right now"],
  },
];

// House style: numbers below ten are written as words, 10 and above as digits.
const NUMBER_WORDS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"];
const numberWord = (n: number) => (n >= 0 && n < 10 ? NUMBER_WORDS[n] : String(n));

const TOTAL_STEPS = FIELDS.length + 1; // + the final name/email/phone step

type Phase = "intro" | "quiz" | "success" | "error";

export default function LeadMagnetModal({
  className = "",
  triggerLabel = "Craft My Future With AI",
}: {
  className?: string;
  triggerLabel?: string;
}) {
  const [open, setOpen] = useState(false);
  const [mounted, setMounted] = useState(false);
  const [phase, setPhase] = useState<Phase>("intro");
  const [stepIndex, setStepIndex] = useState(0); // 0..FIELDS.length-1, then FIELDS.length = contact step
  const [answers, setAnswers] = useState<Record<string, string | string[]>>({});
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [downloadUrl, setDownloadUrl] = useState<string | null>(null);
  const [emailSent, setEmailSent] = useState(false);

  function reset() {
    setPhase("intro");
    setStepIndex(0);
    setAnswers({});
    setName("");
    setEmail("");
    setPhone("");
    setDownloadUrl(null);
    setEmailSent(false);
  }

  function close() {
    setOpen(false);
    reset();
  }

  const onContactStep = stepIndex === FIELDS.length;
  const currentField = onContactStep ? null : FIELDS[stepIndex];

  function isCurrentStepValid(): boolean {
    if (onContactStep) {
      return name.trim().length > 0 && email.trim().length > 3 && email.includes("@");
    }
    if (!currentField) return false;
    const value = answers[currentField.key];
    if (currentField.type === "multi") {
      return Array.isArray(value) && value.length > 0;
    }
    if (currentField.type === "scale") {
      return typeof value === "string" && value !== "";
    }
    return typeof value === "string" && value.trim().length > 0;
  }

  function goNext() {
    if (!isCurrentStepValid()) return;
    if (onContactStep) {
      submit();
      return;
    }
    setStepIndex((i) => i + 1);
  }

  function goBack() {
    setStepIndex((i) => Math.max(0, i - 1));
  }

  function setSingle(key: string, value: string) {
    setAnswers((a) => ({ ...a, [key]: value }));
  }

  function toggleMulti(key: string, value: string, maxSelect?: number) {
    setAnswers((a) => {
      const current = Array.isArray(a[key]) ? (a[key] as string[]) : [];
      const selected = current.includes(value);
      let next: string[];
      if (selected) {
        next = current.filter((v) => v !== value);
      } else if (maxSelect && current.length >= maxSelect) {
        return a; // at the cap, ignore
      } else {
        next = [...current, value];
      }
      return { ...a, [key]: next };
    });
  }

  async function submit() {
    if (submitting) return;
    setSubmitting(true);
    try {
      const res = await fetch(`${API_BASE}/api/leads/website`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, email, phone, answers }),
      });
      const data = await res.json();
      if (!res.ok || !data.lead_magnet_delivery_url) {
        throw new Error(data?.message || "Something went wrong.");
      }
      setDownloadUrl(`${API_BASE}${data.lead_magnet_delivery_url}`);
      setEmailSent(Boolean(data.email_sent));
      setPhase("success");
    } catch (err) {
      // Most common cause: the backend isn't running / isn't reachable at
      // API_BASE (NEXT_PUBLIC_API_URL). Logged so it shows in the browser
      // console instead of failing silently.
      console.error(`Lead magnet request to ${API_BASE} failed:`, err);
      setPhase("error");
    } finally {
      setSubmitting(false);
    }
  }

  useEffect(() => setMounted(true), []);

  // While the pop-up is open: stop the page behind it from scrolling, and
  // let Escape close it.
  useEffect(() => {
    if (!open) return;
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") close();
    };
    window.addEventListener("keydown", onKey);
    return () => {
      document.body.style.overflow = prevOverflow;
      window.removeEventListener("keydown", onKey);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className={
          "mga-cta inline-block rounded bg-mga-coral px-8 py-3 font-semibold text-white shadow-sm transition duration-300 hover:-translate-y-0.5 hover:shadow-lg hover:brightness-95 active:translate-y-0 " +
          className
        }
      >
        {triggerLabel}
      </button>

      {/* Rendered into <body> via a portal, NOT next to the button. The
          buttons live inside sections with scroll-reveal/entrance
          animations, and any ancestor with a CSS transform turns
          `position: fixed` into "fixed to that section" -- which trapped
          the pop-up inside the section, let later page content paint on
          top of it, and stopped the dark backdrop covering the page. */}
      {open && mounted && createPortal(
        <div
          className="mga-backdrop fixed inset-0 z-[100] flex items-center justify-center bg-black/60 p-4"
          role="dialog"
          aria-modal="true"
          aria-label="Your Three-Year Future Snapshot"
          onClick={(e) => {
            if (e.target === e.currentTarget) close();
          }}
        >
          <div className="mga-modal relative max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-lg bg-mga-bgLight p-8 shadow-xl">
            <button
              type="button"
              onClick={close}
              aria-label="Close"
              className="absolute right-4 top-4 rounded bg-black/70 px-3 py-1 text-sm font-medium text-white hover:bg-black/80"
            >
              Close
            </button>

            {phase === "intro" && (
              <div className="text-center">
                <p className="text-lg text-mga-heading">
                  Want to get clearer on your future?
                </p>
                <p className="mt-2 text-2xl font-bold text-mga-coral">
                  Your Three-Year Future Snapshot
                </p>
                <p className="mx-auto mt-3 max-w-sm text-sm italic text-mga-accentBlue">
                  Answer a few quick questions about where you want to go and
                  what may be standing in the way. We&rsquo;ll turn your
                  answers into a personalized report around your goals,
                  priorities, and growth areas &mdash; yours in under a
                  minute.
                </p>

                <ol className="mt-6 space-y-4 text-left">
                  {[
                    {
                      title: "Answer seven quick questions",
                      body: "About a minute — mostly quick picks, a couple of short answers.",
                    },
                    {
                      title: "We build your personalized Growth Blueprint",
                      body: "Matched to exactly what you told us — your goals, your blockers, your pace.",
                    },
                    {
                      title: "Get it instantly, and in your inbox",
                      body: "Download it right here, and we'll email you a copy too.",
                    },
                  ].map((item, i) => (
                    <li key={item.title} className="flex items-start gap-3">
                      <span className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-mga-navy text-sm font-bold text-white">
                        {i + 1}
                      </span>
                      <span>
                        <span className="block font-semibold text-mga-heading">
                          {item.title}
                        </span>
                        <span className="block text-sm text-mga-grayDark">
                          {item.body}
                        </span>
                      </span>
                    </li>
                  ))}
                </ol>

                <button
                  type="button"
                  onClick={() => setPhase("quiz")}
                  className="mt-8 w-full rounded bg-mga-mint px-8 py-3 font-semibold text-white shadow-sm transition hover:bg-mga-mintDark"
                >
                  Start My Free Snapshot →
                </button>
              </div>
            )}

            {phase === "quiz" && (
              <div>
                {/* Progress */}
                <div className="mb-6">
                  <div className="h-1.5 w-full overflow-hidden rounded-full bg-mga-navy/10">
                    <div
                      className="h-full rounded-full bg-mga-mint transition-all"
                      style={{
                        width: `${((stepIndex + 1) / TOTAL_STEPS) * 100}%`,
                      }}
                    />
                  </div>
                  <p className="mt-2 text-center text-xs text-mga-gray">
                    Step {numberWord(stepIndex + 1)} of {numberWord(TOTAL_STEPS)}
                  </p>
                </div>

                {!onContactStep && currentField && (
                  <QuestionField
                    field={currentField}
                    answers={answers}
                    setSingle={setSingle}
                    toggleMulti={toggleMulti}
                  />
                )}

                {onContactStep && (
                  <div>
                    <p className="font-semibold text-mga-heading">
                      Last step — where should we send your Snapshot?
                    </p>
                    <p className="mt-1 text-sm text-mga-grayDark">
                      You&rsquo;ll get it instantly here, and a copy in your
                      inbox too.
                    </p>
                    <div className="mt-3 space-y-3">
                      <div>
                        <label className="block text-sm font-semibold text-mga-heading">
                          Your name
                        </label>
                        <input
                          type="text"
                          value={name}
                          onChange={(e) => setName(e.target.value)}
                          className="mt-1 w-full rounded border border-mga-navy/30 px-3 py-2 text-mga-grayDark focus:border-mga-navy focus:outline-none"
                          placeholder="Jane Doe"
                          autoFocus
                        />
                      </div>
                      <div>
                        <label className="block text-sm font-semibold text-mga-heading">
                          Phone{" "}
                          <span className="font-normal text-mga-gray">
                            (optional)
                          </span>
                        </label>
                        <input
                          type="tel"
                          value={phone}
                          onChange={(e) => setPhone(e.target.value)}
                          className="mt-1 w-full rounded border border-mga-navy/30 px-3 py-2 text-mga-grayDark focus:border-mga-navy focus:outline-none"
                          placeholder="+1 555 000 0000"
                        />
                      </div>
                      <div>
                        <label className="block text-sm font-semibold text-mga-heading">
                          Email
                        </label>
                        <input
                          type="email"
                          value={email}
                          onChange={(e) => setEmail(e.target.value)}
                          className="mt-1 w-full rounded border border-mga-navy/30 px-3 py-2 text-mga-grayDark focus:border-mga-navy focus:outline-none"
                          placeholder="you@example.com"
                        />
                      </div>
                    </div>
                  </div>
                )}

                <div className="mt-8 flex items-center justify-between gap-3">
                  <button
                    type="button"
                    onClick={goBack}
                    disabled={stepIndex === 0}
                    className="rounded px-4 py-2 text-sm font-semibold text-mga-heading transition hover:underline disabled:cursor-not-allowed disabled:opacity-0"
                  >
                    ← Back
                  </button>
                  <button
                    type="button"
                    onClick={goNext}
                    disabled={!isCurrentStepValid() || submitting}
                    className="flex-1 rounded bg-mga-mint px-8 py-3 font-semibold text-white shadow-sm transition hover:bg-mga-mintDark disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {onContactStep
                      ? submitting
                        ? "Building your Snapshot…"
                        : "Get My Free Snapshot"
                      : "Next →"}
                  </button>
                </div>
              </div>
            )}

            {phase === "success" && (
              <div className="text-center">
                <p className="text-2xl font-bold text-mga-coral">
                  Your Future Snapshot is ready 🎉
                </p>
                <p className="mt-3 text-mga-grayDark">
                  It&rsquo;s personalized to what you just told us.{" "}
                  {emailSent
                    ? "We've also sent a copy to your inbox."
                    : "Download it below to keep it handy."}
                </p>
                {downloadUrl && (
                  <a
                    href={downloadUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="mt-6 inline-block w-full rounded bg-mga-mint px-8 py-3 font-semibold text-white shadow-sm transition hover:bg-mga-mintDark"
                  >
                    Download My Future Snapshot
                  </a>
                )}
                <p className="mt-6 text-mga-grayDark">
                  Want to talk it through with Kanth &amp; Shaku?
                </p>
                <a
                  href={BOOKING_URL}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="mt-3 inline-block w-full rounded border-2 border-mga-coral px-8 py-3 font-semibold text-mga-coral transition hover:bg-mga-coral hover:text-white"
                >
                  Book a Free Call
                </a>
              </div>
            )}

            {phase === "error" && (
              <div className="text-center">
                <p className="text-2xl font-bold text-mga-coral">
                  That didn&rsquo;t go through
                </p>
                <p className="mt-3 text-mga-grayDark">
                  Something interrupted building your Snapshot. Please try
                  again.
                </p>
                <button
                  type="button"
                  onClick={() => setPhase("quiz")}
                  className="mt-6 w-full rounded bg-mga-mint px-8 py-3 font-semibold text-white shadow-sm transition hover:bg-mga-mintDark"
                >
                  Try Again
                </button>
              </div>
            )}
          </div>
        </div>,
        document.body
      )}
    </>
  );
}

function QuestionField({
  field,
  answers,
  setSingle,
  toggleMulti,
}: {
  field: Field;
  answers: Record<string, string | string[]>;
  setSingle: (key: string, value: string) => void;
  toggleMulti: (key: string, value: string, maxSelect?: number) => void;
}) {
  if (field.type === "text") {
    const value = (answers[field.key] as string) || "";
    return (
      <div>
        <label className="block font-semibold text-mga-heading">
          {field.label}
        </label>
        {field.helper && (
          <p className="mt-1 text-sm text-mga-gray">{field.helper}</p>
        )}
        <textarea
          value={value}
          onChange={(e) => setSingle(field.key, e.target.value)}
          rows={4}
          className="mt-3 w-full rounded border border-mga-navy/30 px-3 py-2 text-mga-grayDark focus:border-mga-navy focus:outline-none"
          autoFocus
        />
      </div>
    );
  }

  if (field.type === "single") {
    const value = (answers[field.key] as string) || "";
    return (
      <fieldset>
        <legend className="font-semibold text-mga-heading">
          {field.label}
        </legend>
        <div className="mt-3 flex flex-col gap-2">
          {field.options.map((opt) => {
            const selected = value === opt;
            return (
              <button
                key={opt}
                type="button"
                onClick={() => setSingle(field.key, opt)}
                className={
                  "rounded-lg border px-4 py-3 text-left text-sm transition " +
                  (selected
                    ? "border-mga-navy bg-mga-navy text-white"
                    : "border-mga-navy/30 text-mga-grayDark hover:border-mga-navy")
                }
              >
                {opt}
              </button>
            );
          })}
        </div>
      </fieldset>
    );
  }

  if (field.type === "multi") {
    const value = (answers[field.key] as string[]) || [];
    return (
      <fieldset>
        <legend className="font-semibold text-mga-heading">
          {field.label}
        </legend>
        {field.helper && (
          <p className="mt-1 text-sm text-mga-gray">{field.helper}</p>
        )}
        <div className="mt-3 flex flex-wrap gap-2">
          {field.options.map((opt) => {
            const selected = value.includes(opt);
            const atCap = Boolean(
              field.maxSelect && value.length >= field.maxSelect && !selected
            );
            return (
              <button
                key={opt}
                type="button"
                onClick={() => toggleMulti(field.key, opt, field.maxSelect)}
                disabled={atCap}
                className={
                  "rounded-full border px-4 py-2 text-sm transition disabled:cursor-not-allowed disabled:opacity-40 " +
                  (selected
                    ? "border-mga-navy bg-mga-navy text-white"
                    : "border-mga-navy/30 text-mga-grayDark hover:border-mga-navy")
                }
              >
                {opt}
              </button>
            );
          })}
        </div>
      </fieldset>
    );
  }

  // scale
  const scoreValue = (answers[field.key] as string) || "";
  const reasonValue = (answers[field.reasonKey] as string) || "";
  return (
    <div>
      <label className="block font-semibold text-mga-heading">
        {field.label}
      </label>
      <div className="mt-3 flex flex-wrap justify-center gap-2">
        {Array.from({ length: 10 }, (_, i) => String(i + 1)).map((n) => {
          const selected = scoreValue === n;
          return (
            <button
              key={n}
              type="button"
              onClick={() => setSingle(field.key, n)}
              className={
                "flex h-10 w-10 items-center justify-center rounded-full border text-sm font-semibold transition " +
                (selected
                  ? "border-mga-navy bg-mga-navy text-white"
                  : "border-mga-navy/30 text-mga-grayDark hover:border-mga-navy")
              }
            >
              {n}
            </button>
          );
        })}
      </div>
      <div className="mt-2 flex justify-between text-xs text-mga-gray">
        <span>{field.lowLabel}</span>
        <span>{field.highLabel}</span>
      </div>

      <label className="mt-6 block text-sm font-semibold text-mga-heading">
        What made you choose that number?{" "}
        <span className="font-normal text-mga-gray">(optional)</span>
      </label>
      <textarea
        value={reasonValue}
        onChange={(e) => setSingle(field.reasonKey, e.target.value)}
        rows={2}
        className="mt-2 w-full rounded border border-mga-navy/30 px-3 py-2 text-mga-grayDark focus:border-mga-navy focus:outline-none"
      />
    </div>
  );
}
