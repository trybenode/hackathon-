import { Audience } from "@/components/landing/Audience";
import { CallToAction } from "@/components/landing/CallToAction";
import { Capabilities } from "@/components/landing/Capabilities";
import { Comparison } from "@/components/landing/Comparison";
import { Hero } from "@/components/landing/Hero";
import { HowItWorks } from "@/components/landing/HowItWorks";
import { LandingFooter } from "@/components/landing/LandingFooter";
import { LandingHeader } from "@/components/landing/LandingHeader";
import { Problem } from "@/components/landing/Problem";

export default function Home() {
  return (
    // The light blue wash fades out behind the header and hero.
    <div
      id="top"
      className="flex min-h-screen flex-col bg-white bg-gradient-to-b from-primary-50/70 to-white bg-size-[100%_800px] bg-no-repeat"
    >
      <LandingHeader />
      <main className="flex flex-col">
        <Hero />
        <Problem />
        <Comparison />
        <HowItWorks />
        <Capabilities />
        <Audience />
        <CallToAction />
      </main>
      <LandingFooter />
    </div>
  );
}
