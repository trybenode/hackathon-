import { Audience } from "@/components/landing/Audience";
import { CallToAction } from "@/components/landing/CallToAction";
import { Capabilities } from "@/components/landing/Capabilities";
import { Comparison } from "@/components/landing/Comparison";
import { Hero } from "@/components/landing/Hero";
import { HowItWorks } from "@/components/landing/HowItWorks";
import { LandingFooter } from "@/components/landing/LandingFooter";
import { LandingHeader } from "@/components/landing/LandingHeader";
import { Problem } from "@/components/landing/Problem";

/**
 * The hero's soft cyan glows: a strong one in the top-left corner and a fainter
 * one bottom-right, behind the phone, with white between.
 */
const HERO_GLOW = {
  backgroundImage: [
    "radial-gradient(40rem 38rem at 0% 0%, rgb(204 241 252 / 0.85) 0%, rgb(230 248 254 / 0.6) 45%, transparent 75%)",
    "radial-gradient(30rem 30rem at 100% 72%, rgb(204 241 252 / 0.6) 0%, transparent 70%)",
  ].join(", "),
  backgroundSize: "100% 820px",
  backgroundRepeat: "no-repeat",
};

export default function Home() {
  return (
    <div id="top" className="flex min-h-screen flex-col bg-white" style={HERO_GLOW}>
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
