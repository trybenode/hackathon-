import Link from "next/link";
import { Logo } from "@/components/brand/Logo";
import { CONTAINER } from "./Section";
import { GetStartedMenu } from "./GetStartedMenu";
import { SECTIONS } from "./links";

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
      <GetStartedMenu />
    </header>
  );
}
