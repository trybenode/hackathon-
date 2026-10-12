import { CustomerNotifications } from "./CustomerNotifications";

export const metadata = { title: "Notifications" };

export default async function CustomerNotificationsPage({ params }: PageProps<"/j/[token]/notifications">) {
  const { token } = await params;

  return <CustomerNotifications token={token} />;
}
