"use client";

import { useState, type FormEvent } from "react";
import { Button, Input, NigeriaFlagIcon, PencilIcon } from "@/components/ui";
import { cn } from "@/lib/cn";
import { guarantor } from "@/lib/dashboardMock";

export function EditProfile() {
  const [dirty, setDirty] = useState(false);
  const [saved, setSaved] = useState(false);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    // No account model yet, so there is nowhere to save to; the screen shows
    // the interaction and waits for the email/OTP work.
    setSaved(true);
    setDirty(false);
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
              {guarantor.initials}
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

        <Input name="name" label="Name" defaultValue={guarantor.fullName} />

        <Input
          name="email"
          type="email"
          label="Email"
          defaultValue={guarantor.email}
          // The email identifies the account, so it is shown but not editable
          // here; changing it will belong to the sign-in flow.
          readOnly
          className="text-grey-600"
        />

        <Input
          name="phone"
          type="tel"
          inputMode="tel"
          label="Phone Number"
          placeholder="Input your phone"
          lead="+234"
          trailingIcon={<NigeriaFlagIcon />}
        />

        <Input name="address" label="Address" placeholder="Input text" />

        {saved && (
          <p role="status" className="text-body-sm text-success">
            Saved. This screen is not connected to an account yet.
          </p>
        )}

        <Button
          type="submit"
          size="lg"
          disabled={!dirty}
          className={cn("mt-4 self-center rounded-lg px-16", !dirty && "bg-grey-600! text-white! opacity-100!")}
        >
          Save Changes
        </Button>
      </form>
    </main>
  );
}
