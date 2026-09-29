import type { ReactNode } from "react";
import { UploadDemo } from "./UploadDemo";
import {
  Badge,
  Button,
  CheckIcon,
  ExclamationIcon,
  Input,
  MagicStarIcon,
  MagicpenIcon,
  ProgressBar,
  Select,
  Textarea,
  CloseIcon,
  type ButtonSize,
  type ButtonVariant,
} from "@/components/ui";

export const metadata = { title: "Design system" };

const buttonVariants: ButtonVariant[] = ["fill", "outline", "ghost"];
const buttonSizes: ButtonSize[] = ["xl", "lg", "md", "sm"];

const helper = "We'll never share your details. See our Privacy Policy.";

const options = ["Design", "Engineering", "Operations", "Support"].map((label) => ({
  value: label.toLowerCase(),
  label,
  icon: <MagicpenIcon />,
}));


const palette: { group: string; swatches: { name: string; className: string }[] }[] = [
  {
    group: "Primary — cyan",
    // Class names are written in full: Tailwind only sees literal strings in source.
    swatches: [
      { name: "primary-50", className: "bg-primary-50" },
      { name: "primary-100", className: "bg-primary-100" },
      { name: "primary-300", className: "bg-primary-300" },
      { name: "primary-400", className: "bg-primary-400" },
      { name: "primary-500", className: "bg-primary-500" },
    ],
  },
  {
    group: "Secondary — navy",
    swatches: [
      { name: "navy-300", className: "bg-navy-300" },
      { name: "navy-400", className: "bg-navy-400" },
      { name: "navy-500", className: "bg-navy-500" },
    ],
  },
  {
    group: "Neutral",
    swatches: [
      { name: "grey-50", className: "bg-grey-50" },
      { name: "grey-200", className: "bg-grey-200" },
      { name: "grey-400", className: "bg-grey-400" },
      { name: "grey-600", className: "bg-grey-600" },
      { name: "grey-900", className: "bg-grey-900" },
    ],
  },
  {
    group: "Semantic",
    swatches: [
      { name: "error", className: "bg-error" },
      { name: "warning", className: "bg-warning" },
      { name: "info", className: "bg-info" },
      { name: "success", className: "bg-success" },
      { name: "error-light", className: "bg-error-light" },
      { name: "warning-light", className: "bg-warning-light" },
      { name: "info-light", className: "bg-info-light" },
      { name: "success-light", className: "bg-success-light" },
      { name: "success-mid", className: "bg-success-mid" },
      { name: "badge-high", className: "bg-badge-high" },
      { name: "badge-medium", className: "bg-badge-medium" },
      { name: "badge-low", className: "bg-badge-low" },
      { name: "badge-verified", className: "bg-badge-verified" },
      { name: "badge-pending", className: "bg-badge-pending" },
    ],
  },
];

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

      <Section title="Colors">
        <div className="flex flex-col gap-6">
          {palette.map(({ group, swatches }) => (
            <div key={group} className="flex flex-col gap-3">
              <h3 className="text-h3 text-grey-900">{group}</h3>
              <div className="flex flex-wrap gap-4">
                {swatches.map(({ name, className }) => (
                  <div key={name} className="flex w-32 flex-col gap-2">
                    <div className={`h-20 rounded-lg border border-grey-200 ${className}`} />
                    <span className="text-body-sm text-grey-600">{name}</span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </Section>

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
          <Input label="First name" placeholder="Input text" helperText={helper} leadingIcon={<MagicStarIcon />} trailingIcon={<MagicStarIcon />} />
          <Input size="lg" label="First name" placeholder="Input text" helperText={helper} leadingIcon={<MagicStarIcon />} trailingIcon={<MagicStarIcon />} />
          <Input size="lg" labelPlacement="inside" label="First name" helperText={helper} leadingIcon={<MagicStarIcon />} trailingIcon={<MagicStarIcon />} />
          <Input label="First name" defaultValue="Input text" status="success" helperText={helper} leadingIcon={<MagicStarIcon />} />
          <Input size="lg" label="First name" defaultValue="Input text" status="error" helperText="Invalid message" leadingIcon={<MagicStarIcon />} />
          <Input size="lg" labelPlacement="inside" label="First name" defaultValue="Input text" status="error" helperText="Invalid message" leadingIcon={<MagicStarIcon />} />
          <Input label="First name" placeholder="Input text" helperText={helper} leadingIcon={<MagicStarIcon />} disabled />
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

      <Section title="Badges and status">
        <div className="flex flex-col gap-6">
          <div className="flex flex-wrap items-start gap-3">
            <Badge tone="high" dot>
              High
            </Badge>
            <Badge tone="medium" dot>
              Medium
            </Badge>
            <Badge tone="low" dot>
              Low
            </Badge>
          </div>
          <div className="flex flex-wrap items-start gap-3">
            <Badge tone="verified" icon={<CheckIcon width={12} height={12} />}>
              Verified
            </Badge>
            <Badge tone="pending" icon={<ExclamationIcon width={12} height={12} />}>
              Pending
            </Badge>
            <Badge tone="failed" icon={<CloseIcon width={12} height={12} />}>
              Failed
            </Badge>
          </div>
          <div className="flex max-w-xs flex-col gap-3">
            <ProgressBar value={92} showValue label="Trust score" />
            <ProgressBar value={62} tone="warning" showValue label="Completion" />
            <ProgressBar value={30} tone="error" showValue label="Risk" />
          </div>
        </div>
      </Section>

      <Section title="File upload">
        <UploadDemo />
      </Section>

      <Section title="Dropdown input">
        <Grid>
          <Select label="Team" placeholder="Input text" helperText={helper} options={options} leadingIcon={<MagicStarIcon />} />
          <Select size="lg" label="Team" placeholder="Input text" helperText={helper} options={options} leadingIcon={<MagicStarIcon />} />
          <Select label="Team" defaultValue="design" clearable helperText={helper} options={options} leadingIcon={<MagicStarIcon />} />
          <Select size="lg" label="Team" defaultValue="design" clearable helperText={helper} options={options} leadingIcon={<MagicStarIcon />} />
          <Select label="Team" status="error" helperText="Invalid message" options={options} placeholder="Input text" />
          <Select label="Team" placeholder="Input text" helperText={helper} options={options} leadingIcon={<MagicStarIcon />} disabled />
        </Grid>
      </Section>
    </main>
  );
}
