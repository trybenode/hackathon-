import { PeopleIcon } from "@/components/worker/recordIcons";
import { BuildingIcon } from "@/components/developer/icons";
import { CONTAINER, Eyebrow } from "./Section";
import { UserCircleIcon } from "./icons";
import { Wave } from "./Wave";

const AUDIENCES = [
  { icon: UserCircleIcon, title: "For workers", body: "Reputation resets when they move to another platform" },
  { icon: PeopleIcon, title: "For clients", body: "Hiring comes with risk and limited resource." },
  // The Figma repeats the workers' line here.
  { icon: BuildingIcon, title: "For platform", body: "Reputation resets when they move to another platform" },
];

export function Problem() {
  return (
    <section aria-labelledby="problem-heading" className="relative -mt-8 lg:-mt-16">
      <Wave edge="top" />
      <div className="bg-primary-50">
        <div className={`${CONTAINER} grid gap-10 py-10 lg:grid-cols-[minmax(0,320px)_1fr] lg:gap-16`}>
          <div className="flex flex-col gap-3">
            <Eyebrow>The problem</Eyebrow>
            <h2 id="problem-heading" className="text-h3 font-semibold text-grey-900 lg:text-[28px] lg:leading-9">
              Trust breaks when the platforms changes.
            </h2>
          </div>
          <ul className="grid gap-8 sm:grid-cols-3">
            {AUDIENCES.map(({ icon: Icon, title, body }) => (
              <li key={title} className="flex flex-col gap-3 border-l border-grey-400 pl-4">
                <Icon className="text-navy-400" width={22} height={22} />
                <span className="text-body-sm font-semibold text-grey-900">{title}</span>
                <span className="text-body-sm text-grey-800">{body}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
      <Wave edge="bottom" />
    </section>
  );
}
