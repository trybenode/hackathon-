"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";
import { Button, Input, NigeriaFlagIcon, PencilIcon } from "@/components/ui";
import { cn } from "@/lib/cn";
import { ApiError, getProfile, updateProfile, type Profile } from "@/lib/guarantor";

/** Initials for the avatar, e.g. "Daniel Peters" becomes DP. */
function initialsOf(name: string) {
  return name
    .split(" ")
    .map((part) => part[0])
    .filter(Boolean)
    .slice(0, 2)
    .join("")
    .toUpperCase();
}

/** The API stores the full number; the field shows it without the dial code. */
const DIAL_CODE = "+234";

function withoutDialCode(phone: string | null) {
  if (!phone) return "";
  return phone.startsWith(DIAL_CODE) ? phone.slice(DIAL_CODE.length) : phone;
}

export function EditProfile() {
  const router = useRouter();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const loaded = await getProfile();
        if (!cancelled) setProfile(loaded);
      } catch (cause) {
        if (cancelled) return;
        if (cause instanceof ApiError && cause.status === 401) {
          router.replace("/sign-in");
          return;
        }
        setError("Could not load your profile.");
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [router]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError(null);

    const data = new FormData(event.currentTarget);
    const localPhone = String(data.get("phone") ?? "").trim();

    try {
      const updated = await updateProfile({
        display_name: String(data.get("name") ?? "").trim(),
        phone: localPhone ? `${DIAL_CODE}${localPhone.replace(/^0+/, "")}` : null,
        address: String(data.get("address") ?? "").trim() || null,
      });
      setProfile(updated);
      setSaved(true);
      setDirty(false);
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : "Could not save your changes.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <main className="flex flex-col">
      <header className="border-b border-stroke px-6 pt-8 pb-5">
        <h1 className="text-body-lg font-semibold text-grey-900">Edit Profile</h1>
      </header>

      <form
        onSubmit={handleSubmit}
        onChange={() => {
          setDirty(true);
          setSaved(false);
        }}
        className="flex flex-col gap-5 px-6 pt-10"
      >
        <div className="flex justify-center">
          <span className="relative">
            <span className="flex h-24 w-24 items-center justify-center rounded-pill bg-primary-500 text-h2 font-medium text-white">
              {profile ? initialsOf(profile.display_name) : "—"}
            </span>
            <button
              type="button"
              aria-label="Change photo"
              className="absolute right-1 bottom-1 flex h-7 w-7 items-center justify-center rounded-pill border-2 border-white bg-primary-400 text-white"
            >
              <PencilIcon />
            </button>
          </span>
        </div>

        {/* Keyed on the loaded value so the field picks it up once it arrives. */}
        <Input
          key={`name-${profile?.display_name}`}
          name="name"
          label="Name"
          defaultValue={profile?.display_name ?? ""}
          required
        />

        <Input
          key={`email-${profile?.email}`}
          name="email"
          type="email"
          label="Email"
          defaultValue={profile?.email ?? ""}
          // The email identifies the account, so it changes through sign-in,
          // not here.
          readOnly
          className="text-grey-600"
        />

        <Input
          key={`phone-${profile?.phone}`}
          name="phone"
          type="tel"
          inputMode="tel"
          label="Phone Number"
          placeholder="Input your phone"
          defaultValue={withoutDialCode(profile?.phone ?? null)}
          lead={DIAL_CODE}
          trailingIcon={<NigeriaFlagIcon />}
        />

        <Input
          key={`address-${profile?.address}`}
          name="address"
          label="Address"
          placeholder="Input text"
          defaultValue={profile?.address ?? ""}
        />

        {error && (
          <p role="alert" className="text-body-sm text-error">
            {error}
          </p>
        )}
        {saved && (
          <p role="status" className="text-body-sm text-success">
            Saved.
          </p>
        )}

        <Button
          type="submit"
          size="lg"
          disabled={!dirty || saving || !profile}
          className={cn(
            "mt-4 self-center rounded-lg px-16",
            (!dirty || saving) && "bg-grey-600! text-white! opacity-100!",
          )}
        >
          {saving ? "Saving…" : "Save Changes"}
        </Button>
      </form>
    </main>
  );
}
