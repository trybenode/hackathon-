import { CustomerJob } from "./CustomerJob";

export const metadata = { title: "Your job" };

/**
 * The job link a worker shares. The customer needs no account: this page is
 * their whole journey, from hiring and paying to releasing or disputing, and
 * every email links back to it.
 */
export default async function CustomerJobPage({ params }: PageProps<"/j/[token]">) {
  const { token } = await params;

  return <CustomerJob token={token} />;
}
