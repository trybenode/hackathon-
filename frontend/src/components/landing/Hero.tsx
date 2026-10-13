import Image from "next/image";
import { ArrowRightIcon } from "@/components/worker/icons";
import { CONTAINER, Eyebrow } from "./Section";
import { LinkButton } from "./LinkButton";
import { LINKS } from "./links";

export function Hero() {
  return (
    <section className={`${CONTAINER} grid items-center gap-12 pt-10 lg:grid-cols-[1fr_auto] lg:pt-16`}>
      <div className="flex flex-col gap-6 lg:pb-24">
        <Eyebrow>Hackathon MVP</Eyebrow>
        <h1 className="text-h1 font-bold text-grey-900 lg:text-display">
          Identity is not Trust
          <span className="block max-w-[480px] text-primary-500">We built the missing layer.</span>
        </h1>
        <p className="max-w-md text-body-md text-grey-800">
          A trust infrastructure that turns verified identity, work outcomes and protections into a
          portable reputation for gig workers
        </p>
        <div className="flex flex-wrap gap-4 pt-2">
          <LinkButton href={LINKS.workerSignUp}>
            View live demo <ArrowRightIcon />
          </LinkButton>
          <LinkButton href="#how-it-works" variant="outline">
            How it works
          </LinkButton>
        </div>
      </div>

      {/* The design shows the top of the phone, cut off by the wave below. */}
      <div className="mx-auto h-[380px] w-[260px] overflow-hidden sm:h-[460px] sm:w-[320px] lg:mx-0">
        <Image
          src="/landing/phone.webp"
          alt="A worker's portable record: an 87% trust score, 42 completed jobs and 95% on time"
          width={851}
          height={1849}
          priority
          // Served as-is: Vercel Services doesn't route /_next/image.
          unoptimized
          className="h-auto w-full"
        />
      </div>
    </section>
  );
}
