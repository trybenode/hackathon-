import { ShieldCheckIcon } from "@/components/developer/icons";
import { CONTAINER, Eyebrow, SectionHeading } from "./Section";
import { CodeIcon, HandshakeIcon, UserCircleIcon } from "./icons";

const CAPABILITIES = [
  {
    icon: HandshakeIcon,
    title: "Trust-Band Scoring",
    body: "Turns verified identity, work history, and performance into a clear trust assessment to support more informed hiring decisions.",
  },
  {
    icon: ShieldCheckIcon,
    title: "Escrow-Backed Guarantee",
    body: "Connects protected payments with a digital guarantee, helping reduce hiring risks and providing a clear process for handling disputes.",
  },
  {
    icon: UserCircleIcon,
    title: "Portable Work Record",
    body: "Builds a verifiable record of completed jobs and work performance that workers can carry across platforms to grow their reputation.",
  },
  {
    icon: CodeIcon,
    title: "Platform API",
    body: "Enables platforms to integrate trust verification and worker reputation into their existing systems without building the entire infrastructure themselves.",
  },
];

export function Capabilities() {
  return (
    <section id="features" aria-labelledby="features-heading" className={`${CONTAINER} flex scroll-mt-6 flex-col items-center gap-10 py-16`}>
      <div className="flex max-w-2xl flex-col items-center gap-3 text-center">
        <Eyebrow>Key capabilities</Eyebrow>
        <SectionHeading>
          <span id="features-heading">The infrastructure behind trusted work.</span>
        </SectionHeading>
        <p className="text-body-sm text-grey-800">
          Explore the tools that make gig work safer and more reliable, from verified worker reputations and
          protected payments to portable work records and seamless platform integration.
        </p>
      </div>
      {/* Three to a row, the fourth centred under them. */}
      <ul className="flex w-full flex-wrap justify-center gap-6">
        {CAPABILITIES.map(({ icon: Icon, title, body }) => (
          <li
            key={title}
            className="flex w-full flex-col gap-4 rounded-lg border border-primary-100 bg-white p-6 transition-shadow hover:shadow-[0_8px_20px_rgb(6_182_233/0.18)] sm:w-[calc(50%-12px)] lg:w-[calc((100%-48px)/3)] lg:max-w-[368px]"
          >
            <span className="flex h-10 w-10 items-center justify-center rounded-pill bg-primary-50 text-primary-500">
              <Icon width={20} height={20} />
            </span>
            <span className="text-body-sm font-semibold text-grey-900">{title}</span>
            <span className="text-body-sm text-grey-800">{body}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
