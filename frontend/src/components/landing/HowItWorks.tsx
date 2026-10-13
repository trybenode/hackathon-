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
      <div className="flex flex-col items-center gap-3 text-center lg:items-start lg:text-left">
        <Eyebrow>How it works</Eyebrow>
        <SectionHeading>
          <span id="how-heading">
            Build your reputation once.
            <br />
            Take it with you.
          </span>
        </SectionHeading>
      </div>
      {/* Below desktop the steps stack, centred, with the trail running down
          between them; on desktop it runs across from number to number. */}
      <ol className="flex flex-col items-center lg:grid lg:grid-cols-4 lg:items-start lg:px-12">
        {STEPS.map((step, index) => {
          const last = index === STEPS.length - 1;
          return (
            <li key={step.title} className="flex flex-col items-center gap-3 text-center lg:items-start lg:text-left">
              <div className="flex w-full items-center justify-center lg:justify-start">
                <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-pill bg-primary-500 text-xs font-semibold text-white">
                  {index + 1}
                </span>
                {!last && <span aria-hidden className="hidden h-px flex-1 bg-primary-500 lg:block" />}
              </div>
              <span className="text-body-sm font-semibold text-grey-900">{step.title}</span>
              <span className="max-w-[220px] text-body-sm text-grey-800 lg:max-w-[200px]">{step.body}</span>
              {!last && <span aria-hidden className="mb-3 h-10 w-px bg-primary-500 lg:hidden" />}
            </li>
          );
        })}
      </ol>
    </section>
  );
}
