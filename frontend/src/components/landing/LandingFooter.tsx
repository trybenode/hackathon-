import type { ReactNode } from "react";
import { Logo } from "@/components/brand/Logo";
import { CONTAINER, DEEP_BLUE } from "./Section";
import { InstagramIcon } from "./icons";
import { CONTACT, SECTIONS } from "./links";

function Column({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-4">
      <h2 className="text-body-sm text-white/60">{title}</h2>
      <ul className="flex flex-col gap-3 text-body-sm text-white">{children}</ul>
    </div>
  );
}

export function LandingFooter() {
  const instagram = (
    <>
      <InstagramIcon /> Instagram
    </>
  );

  return (
    <footer>
      <div className={DEEP_BLUE}>
        <div className={`${CONTAINER} grid gap-10 py-14 sm:grid-cols-2 lg:grid-cols-[1.2fr_1fr_1fr_1fr]`}>
          <Logo tone="light" />
          <Column title="Quick Links">
            <li>
              <a href="#top" className="hover:underline">
                Home
              </a>
            </li>
            {SECTIONS.map((section) => (
              <li key={section.id}>
                <a href={`#${section.id}`} className="hover:underline">
                  {section.label}
                </a>
              </li>
            ))}
          </Column>
          <Column title="Social Media">
            <li>
              {CONTACT.instagram ? (
                <a href={CONTACT.instagram} target="_blank" rel="noreferrer" className="flex items-center gap-2 hover:underline">
                  {instagram}
                </a>
              ) : (
                <span className="flex items-center gap-2">{instagram}</span>
              )}
            </li>
          </Column>
          <Column title="Contact Information">
            <li>
              <a href={`mailto:${CONTACT.email}`} className="hover:underline">
                {CONTACT.email}
              </a>
            </li>
            <li>
              <a href={`tel:${CONTACT.phone.replaceAll(" ", "")}`} className="hover:underline">
                {CONTACT.phone}
              </a>
            </li>
          </Column>
        </div>
      </div>
      <p className="bg-grey-800 py-3 text-center text-xs text-white">Hackathon MVP · 2026</p>
    </footer>
  );
}
