import type { RecordAssessment } from "@/lib/workerRecord";
import { formatPercent } from "@/lib/workerRecord";

export function AssessmentConfidence({ assessment }: { assessment: RecordAssessment }) {
  return <div className="text-body-sm text-grey-600"><p>Evidence confidence: {formatPercent(assessment.confidence)}</p><p className="mt-1">Confidence describes the evidence supporting this model score. The score is not a probability or guarantee.</p><p className="mt-2">{assessment.explanation_summary}</p></div>;
}
