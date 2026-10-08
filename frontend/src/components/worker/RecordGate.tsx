import type { ReactNode } from "react";

/** Shows loading or the error until the worker's record has arrived. */
export function RecordGate({
  loading,
  error,
  children,
}: {
  loading: boolean;
  error: string | null;
  children: ReactNode;
}) {
  if (loading) {
    return (
      <p role="status" className="px-6 pt-8 text-body-sm text-grey-600">
        Loading…
      </p>
    );
  }
  if (error) {
    return (
      <p role="alert" className="px-6 pt-8 text-body-sm text-error">
        {error}
      </p>
    );
  }
  return <>{children}</>;
}
