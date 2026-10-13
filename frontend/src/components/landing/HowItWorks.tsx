import { CONTAINER, Eyebrow, SectionHeading } from "./Section";

const STEPS = [
  { title: "Verify", body: "A platform or individual checks the worker's trust profile." },
  { title: "Protect", body: "Escrow and coverage create protection around the job." },
  { title: "Complete", body: "The worker and client confirm the outcome." },
  { title: "Build reputation", body: "The verified outcome updates the worker's portable record" },
];

export function HowItWorks() {
  return (
    <section id="how-it-works" aria-labelledby="how-heading" className={`${CONTAINER} flex scroll-mt-6 flex-col gap-10 py-16`}>
      <div className="flex flex-col gap-3">
        <Eyebrow>How it works</Eyebrow>
        <SectionHeading>
          <span id="how-heading">
            Build your reputation once.
            <br />
            Take it with you.
          </span>
        </SectionHeading>
      </div>
      <ol className="grid gap-8 sm:grid-cols-2 lg:grid-cols-4 lg:gap-0 lg:px-12">
        {STEPS.map((step, index) => (
          <li key={step.title} className="flex flex-col gap-3">
            <div className="flex items-center">
              <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-pill bg-primary-500 text-xs font-semibold text-white">
                {index + 1}
              </span>
              {/* The line runs on to the next step's number. */}
              {index < STEPS.length - 1 && <span aria-hidden className="hidden h-px flex-1 bg-primary-500 lg:block" />}
            </div>
            <span className="text-body-sm font-semibold text-grey-900">{step.title}</span>
            <span className="max-w-[200px] text-body-sm text-grey-800">{step.body}</span>
          </li>
        ))}
      </ol>
    </section>
  );
}
