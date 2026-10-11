"use client";

import { useId } from "react";
import { cn } from "@/lib/cn";
import type { AccessGroup, ApiKeyList } from "@/lib/developer";

type Groups = ApiKeyList["access_groups"];

function Tick() {
  return (
    <svg viewBox="0 0 16 16" width="12" height="12" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="m3.5 8.5 3 3 6-7" />
    </svg>
  );
}

/** A choice control drawn like the developer radios: filled with a tick when on. */
function Mark({ on, square = false }: { on: boolean; square?: boolean }) {
  return (
    <span
      aria-hidden
      className={cn(
        "mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center transition-colors",
        square ? "rounded-md" : "rounded-pill",
        "peer-focus-visible:ring-2 peer-focus-visible:ring-primary-300 peer-focus-visible:ring-offset-2",
        on ? "bg-primary-500 text-white" : "border border-grey-200 bg-grey-50",
      )}
    >
      {on && <Tick />}
    </span>
  );
}

/**
 * What a key may do: full access (future features included), or a choice of
 * the access groups. `value` is null for full access.
 */
export function AccessPicker({
  groups,
  value,
  onChange,
}: {
  groups: Groups;
  value: AccessGroup[] | null;
  onChange: (value: AccessGroup[] | null) => void;
}) {
  const name = useId();
  const full = value === null;
  const chosen = new Set(value ?? []);

  function toggle(group: AccessGroup) {
    const next = new Set(chosen);
    if (next.has(group)) next.delete(group);
    else next.add(group);
    onChange(groups.map((item) => item.id).filter((id) => next.has(id)));
  }

  return (
    <fieldset className="flex flex-col gap-3">
      <legend className="pb-3 text-body-sm font-medium text-grey-600">Access</legend>

      <label className="flex cursor-pointer items-start gap-3">
        <input type="radio" name={name} checked={full} onChange={() => onChange(null)} className="peer sr-only" />
        <Mark on={full} />
        <span className="flex flex-col">
          <span className="text-body-md text-grey-900">Full access</span>
          <span className="text-xs leading-4 text-grey-600">Everything the API offers, including features added later.</span>
        </span>
      </label>

      <label className="flex cursor-pointer items-start gap-3">
        <input
          type="radio"
          name={name}
          checked={!full}
          onChange={() => onChange(value ?? [groups[0].id])}
          className="peer sr-only"
        />
        <Mark on={!full} />
        <span className="flex flex-col">
          <span className="text-body-md text-grey-900">Choose access</span>
          <span className="text-xs leading-4 text-grey-600">Only what this key needs. A worker&rsquo;s approval still applies on top.</span>
        </span>
      </label>

      {!full && (
        <div className="ml-8 flex flex-col gap-3 rounded-lg border border-stroke p-3">
          {groups.map((group) => (
            <label key={group.id} className="flex cursor-pointer items-start gap-3">
              <input
                type="checkbox"
                checked={chosen.has(group.id)}
                onChange={() => toggle(group.id)}
                className="peer sr-only"
              />
              <Mark on={chosen.has(group.id)} square />
              <span className="flex flex-col">
                <span className="text-body-sm font-medium text-grey-900">{group.label}</span>
                <span className="text-xs leading-4 text-grey-600">{group.description}</span>
              </span>
            </label>
          ))}
        </div>
      )}
    </fieldset>
  );
}

/** The key's access as short chips: "Full access", or each chosen group. */
export function AccessChips({ groups, scopes }: { groups: Groups; scopes: AccessGroup[] | null }) {
  const labels = scopes === null ? ["Full access"] : scopes.map((id) => groups.find((group) => group.id === id)?.label ?? id);
  return (
    <span className="flex flex-wrap gap-1.5">
      {labels.map((label) => (
        <span
          key={label}
          className={cn(
            "rounded-md px-2 py-0.5 text-xs",
            scopes === null ? "bg-primary-50 text-grey-900" : "bg-grey-50 text-grey-800",
          )}
        >
          {label}
        </span>
      ))}
    </span>
  );
}
