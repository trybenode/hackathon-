import { Audience } from "@/components/landing/Audience";
import { Capabilities } from "@/components/landing/Capabilities";
import { Comparison } from "@/components/landing/Comparison";
import { Hero } from "@/components/landing/Hero";
import { HowItWorks } from "@/components/landing/HowItWorks";
import { LandingHeader } from "@/components/landing/LandingHeader";
import { Problem } from "@/components/landing/Problem";

export default function Home() {
  return (
    <div className="flex min-h-screen flex-col bg-gradient-to-b from-primary-50/60 via-white to-white">
      <LandingHeader />
      <main className="flex flex-col">
        <Hero />
        <Problem />
        <Comparison />
        <HowItWorks />
        <Capabilities />
        <Audience />
      </main>
    </div>
  );
}
