import { CheckIcon } from "@/components/ui";
import { formatNairaWhole, formatNumericDate, type RecordOutcome } from "@/lib/workerRecord";

/** The "Verified outcomes" card, on the record and on the full history. */
export function OutcomeList({ outcomes }: { outcomes: RecordOutcome[] }) {
  return (
    <div className="overflow-hidden rounded-lg bg-white shadow-1">
      <h2 className="bg-primary-25 px-3 py-4 text-body-md text-grey-900">Verified outcomes</h2>
      {outcomes.length === 0 ? (
        <p className="border-t border-stroke px-3 py-4 text-body-sm text-grey-600">
          No verified outcomes yet.
        </p>
      ) : (
        <ul>
          {outcomes.map((outcome) => (
            <li key={outcome.id} className="flex items-center gap-3 border-t border-stroke px-3 py-2">
              <CheckIcon className="shrink-0 text-grey-900" />
              <span className="flex flex-1 flex-col">
                <span className="text-body-sm font-medium text-grey-900">{outcome.title}</span>
                <span className="text-body-sm text-grey-800">
                  {formatNumericDate(outcome.occurred_at)}· {formatNairaWhole(outcome.amount)}
                </span>
              </span>
              <span className="text-xs leading-4 text-grey-900">{outcome.status}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
