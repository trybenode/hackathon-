import { DeclinedNotice } from "./DeclinedNotice";

export const metadata = { title: "Request declined" };

export default async function DeclinedPage({ params }: PageProps<"/guarantor/[id]/declined">) {
  const { id } = await params;

  return <DeclinedNotice instrumentId={id} />;
}
