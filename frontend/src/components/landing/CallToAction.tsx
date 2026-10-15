import { ArrowRightIcon } from "@/components/worker/icons";
import { CONTAINER } from "./Section";
import { LinkButton } from "./LinkButton";
import { LINKS } from "./links";

export function CallToAction() {
  return (
    <section aria-labelledby="cta-heading" className={`${CONTAINER} py-16`}>
      <div className="flex flex-col gap-6 rounded-lg bg-gradient-to-r from-primary-500 to-[#0a8fc4] px-6 py-8 md:flex-row md:items-center md:justify-between md:px-8">
        <div className="flex flex-col gap-2">
          <h2 id="cta-heading" className="text-h3 font-semibold text-white">
            Make trust part of every job.
          </h2>
          <p className="text-body-sm text-white/90">
            Give workers a reputation that can be verified, shared and carried forward
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-4">
          <LinkButton href={LINKS.liveDemo} variant="light">
            View live demo <ArrowRightIcon />
          </LinkButton>
          <LinkButton href={LINKS.technicalDocs} variant="text">
            View technical docs
          </LinkButton>
        </div>
      </div>
    </section>
  );
}
