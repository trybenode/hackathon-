import Link from "next/link";
import { Logo } from "@/components/brand/Logo";
import { CONTAINER } from "./Section";
import { LinkButton } from "./LinkButton";
import { LINKS, SECTIONS } from "./links";

export function LandingHeader() {
  return (
    <header className={`${CONTAINER} flex h-20 items-center justify-between gap-6`}>
      <Link href="/" aria-label="Home">
        <Logo />
      </Link>
      <nav aria-label="Sections" className="hidden items-center gap-8 md:flex">
        {SECTIONS.map((section) => (
          <a key={section.id} href={`#${section.id}`} className="text-body-sm text-grey-900 hover:text-primary-500">
            {section.label}
          </a>
        ))}
      </nav>
      {/* Goes to worker sign-up until the Figma's worker/platform chooser is in. */}
      <LinkButton href={LINKS.workerSignUp} size="sm">
        Get Started
      </LinkButton>
    </header>
  );
}
