import Image from "next/image";

/** The illustration that heads the onboarding screens for workers and guarantors. */
export function OnboardingHero() {
  return (
    <div className="relative mt-6 aspect-[400/235] w-full overflow-hidden">
      <Image
        src="/guarantor-hero.webp"
        alt=""
        fill
        priority
        sizes="(max-width: 448px) 100vw, 448px"
        className="object-cover"
        style={{ objectPosition: "50% 37%" }}
      />
    </div>
  );
}
