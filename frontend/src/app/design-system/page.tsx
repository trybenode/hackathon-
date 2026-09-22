import type { ReactNode } from "react";
import { Button, Input, Select, Textarea, type ButtonSize, type ButtonVariant } from "@/components/ui";

export const metadata = { title: "Design system" };

const buttonVariants: ButtonVariant[] = ["fill", "outline", "ghost"];
const buttonSizes: ButtonSize[] = ["xl", "lg", "md", "sm"];

const helper = "We'll never share your details. See our Privacy Policy.";

function StarIcon() {
  return (
    <svg viewBox="0 0 16 16" width="16" height="16" fill="currentColor" aria-hidden>
      <path d="M8 1.5l1.9 4 4.4.5-3.3 3 .9 4.3L8 11.1l-3.9 2.2.9-4.3-3.3-3 4.4-.5z" />
    </svg>
  );
}

const options = ["Design", "Engineering", "Operations", "Support"].map((label) => ({
  value: label.toLowerCase(),
  label,
  icon: <StarIcon />,
}));

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="flex flex-col gap-6 border-t border-grey-200 pt-8">
      <h2 className="text-h2 text-navy-500">{title}</h2>
      {children}
    </section>
  );
}

function Grid({ children }: { children: ReactNode }) {
  return <div className="grid gap-8 md:grid-cols-2 lg:grid-cols-3">{children}</div>;
}

export default function DesignSystemPage() {
  return (
    <main className="mx-auto flex w-full max-w-6xl flex-col gap-12 px-4 py-12 sm:px-8">
      <h1 className="text-display text-navy-500">Design system</h1>

      <Section title="Buttons">
        <div className="flex flex-col gap-6">
          {buttonVariants.map((variant) => (
            <div key={variant} className="flex flex-wrap items-center gap-6">
              <span className="w-20 text-body-sm capitalize text-grey-600">{variant}</span>
              {buttonSizes.map((size) => (
                <Button key={size} variant={variant} size={size}>
                  Button
                </Button>
              ))}
              <Button variant={variant} disabled>
                Disabled
              </Button>
            </div>
          ))}
        </div>
      </Section>

      <Section title="Input fields">
        <Grid>
          <Input label="First name" placeholder="Input text" helperText={helper} leadingIcon={<StarIcon />} trailingIcon={<StarIcon />} />
          <Input size="lg" label="First name" placeholder="Input text" helperText={helper} leadingIcon={<StarIcon />} trailingIcon={<StarIcon />} />
          <Input size="lg" labelPlacement="inside" label="First name" helperText={helper} leadingIcon={<StarIcon />} trailingIcon={<StarIcon />} />
          <Input label="First name" defaultValue="Input text" status="success" helperText={helper} leadingIcon={<StarIcon />} />
          <Input size="lg" label="First name" defaultValue="Input text" status="error" helperText="Invalid message" leadingIcon={<StarIcon />} />
          <Input size="lg" labelPlacement="inside" label="First name" defaultValue="Input text" status="error" helperText="Invalid message" leadingIcon={<StarIcon />} />
          <Input label="First name" placeholder="Input text" helperText={helper} leadingIcon={<StarIcon />} disabled />
          <Input size="lg" label="First name" placeholder="Input text" helperText={helper} disabled />
          <Input size="lg" labelPlacement="inside" label="First name" helperText={helper} disabled />
        </Grid>
      </Section>

      <Section title="Grouped input">
        <Grid>
          <Input label="Website" lead="https://" placeholder="example.com" helperText={helper} />
          <Input size="lg" label="Phone" lead="+234" placeholder="801 234 5678" helperText={helper} />
          <Input size="lg" label="Phone" lead="+234" defaultValue="801 234 5678" status="success" helperText={helper} />
          <Input label="Phone" lead="+234" defaultValue="801" status="error" helperText="Invalid message" />
          <Input label="Phone" lead="+234" placeholder="801 234 5678" helperText={helper} disabled />
        </Grid>
      </Section>

      <Section title="Multiline input">
        <Grid>
          <Textarea label="Bio" placeholder="Input text" helperText={helper} showCount maxLength={234} />
          <Textarea size="lg" label="Bio" placeholder="Input text" helperText={helper} showCount maxLength={234} />
          <Textarea size="lg" labelPlacement="inside" label="Bio" helperText={helper} />
          <Textarea label="Bio" status="error" helperText="Invalid message" defaultValue="Too short" showCount maxLength={234} />
          <Textarea label="Bio" placeholder="Input text" helperText={helper} disabled showCount maxLength={234} />
        </Grid>
      </Section>

      <Section title="Dropdown input">
        <Grid>
          <Select label="Team" placeholder="Input text" helperText={helper} options={options} leadingIcon={<StarIcon />} />
          <Select size="lg" label="Team" placeholder="Input text" helperText={helper} options={options} leadingIcon={<StarIcon />} />
          <Select label="Team" defaultValue="design" clearable helperText={helper} options={options} />
          <Select size="lg" label="Team" defaultValue="design" clearable helperText={helper} options={options} />
          <Select label="Team" status="error" helperText="Invalid message" options={options} placeholder="Input text" />
          <Select label="Team" placeholder="Input text" helperText={helper} options={options} leadingIcon={<StarIcon />} disabled />
        </Grid>
      </Section>
    </main>
  );
}
