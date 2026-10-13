import { BuildingIcon } from "@/components/developer/icons";
import { PeopleIcon } from "@/components/worker/recordIcons";
import { CONTAINER, Eyebrow, SectionHeading, TINTED } from "./Section";
import { UserCircleIcon } from "./icons";

const AUDIENCES = [
  { icon: BuildingIcon, title: "For platforms", body: "Reduce cutouts and build stronger trust into your marketplace." },
  { icon: UserCircleIcon, title: "For workers", body: "Carry verified reputation across platforms." },
  { icon: PeopleIcon, title: "For clients", body: "Hire with greater confidence, even outside major platforms." },
];

export function Audience() {
  return (
    <section id="who-its-for" aria-labelledby="audience-heading" className={`${TINTED} scroll-mt-6`}>
      <div className={`${CONTAINER} flex flex-col gap-10 py-16`}>
        <div className="flex flex-col gap-3">
          <Eyebrow>Who it&rsquo;s for</Eyebrow>
          <SectionHeading>
            <span id="audience-heading">Built for everyone who depends on trust</span>
          </SectionHeading>
          <p className="max-w-2xl text-body-sm text-grey-800">
            Built for platforms, workers, and individuals who want safer hiring, trusted work relationships, and a
            reputation that grows with every verified job.
          </p>
        </div>
        <ul className="grid gap-6 md:grid-cols-3">
          {AUDIENCES.map(({ icon: Icon, title, body }) => (
            <li key={title} className="flex flex-col gap-3 rounded-lg border border-primary-100 bg-white p-6 shadow-1">
              <span className="flex items-center gap-3 text-body-sm font-medium text-grey-900">
                <Icon width={20} height={20} className="shrink-0 text-navy-400" />
                {title}
              </span>
              <span className="pl-8 text-body-sm text-grey-800">{body}</span>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
