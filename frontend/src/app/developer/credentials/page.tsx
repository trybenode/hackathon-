import { redirect } from "next/navigation";

/** Credentials moved to API keys, where they are created and managed. */
export default function DeveloperCredentialsPage() {
  redirect("/developer/keys");
}
