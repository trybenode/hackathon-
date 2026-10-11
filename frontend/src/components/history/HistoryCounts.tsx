import type { HistoryCounts as Counts } from "@/lib/history";
import { english, type Dictionary } from "@/lib/historyLanguage";

/** Public whitelist of aggregate declarations; confirmed contact is not independent job verification. */
export function HistoryCounts({ counts, dictionary = english }: { counts?: Counts; dictionary?: Dictionary }) {
  if (!counts) return null;
  return <section className="flex flex-col gap-3 rounded-xl border border-stroke p-4"><h2 className="font-semibold">{dictionary.workHistory}</h2><dl className="grid grid-cols-2 gap-3"><div><dt>{dictionary.declaredCount}</dt><dd>{counts.declared_jobs}</dd></div><div><dt>{dictionary.attestedCount}</dt><dd>{counts.contact_attested_jobs}</dd></div><div><dt>{dictionary.sandboxCount}</dt><dd>{counts.sandbox_attested_jobs}</dd></div><div><dt>{dictionary.matchedCount}</dt><dd>{counts.matched_customer_jobs}</dd></div></dl><p>{dictionary.scoreUnchanged}</p></section>;
}
