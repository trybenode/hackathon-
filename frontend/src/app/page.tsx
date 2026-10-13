import { Hero } from "@/components/landing/Hero";
import { LandingHeader } from "@/components/landing/LandingHeader";
import { Problem } from "@/components/landing/Problem";

export default function Home() {
  return (
    <div className="flex min-h-screen flex-col bg-gradient-to-b from-primary-50/60 via-white to-white">
      <LandingHeader />
      <main className="flex flex-col">
        <Hero />
        <Problem />
      </main>
    </div>
  );
}
