/**
 * Purpose: Render the initial trust-infrastructure product shell and system status.
 * Dependencies: Next.js App Router and Tailwind CSS classes.
 * Used by: the root route at `/`.
 */

import { PortableRecord } from "./worker/profile/record/PortableRecord";

export default function Home() {
  return (
    <main className="min-h-screen bg-[#f5f1e8] text-[#18211b]">
      <div className="mx-auto flex min-h-screen max-w-7xl flex-col px-6 py-6 sm:px-10 lg:px-14">
        <header className="flex items-center justify-between border-b border-[#18211b]/15 pb-5">
          <div className="flex items-center gap-3">
            <span className="h-3 w-3 rounded-full bg-[#e35d3f]" />
            <span className="text-sm font-semibold tracking-[0.18em] uppercase">
              Trust Infrastructure
            </span>
          </div>
          <span className="font-mono text-xs text-[#18211b]/60">MVP / 0.1.0</span>
        </header>

        <section className="grid flex-1 items-center gap-12 py-16 lg:grid-cols-[1.2fr_0.8fr]">
          <div>
            <p className="mb-6 font-mono text-xs tracking-[0.2em] text-[#e35d3f] uppercase">
              Shared trust layer for independent work
            </p>
            <h1 className="max-w-4xl text-5xl leading-[0.95] font-semibold tracking-[-0.04em] sm:text-7xl">
              Make reliability portable.
            </h1>
            <p className="mt-8 max-w-xl text-lg leading-8 text-[#18211b]/70">
              The platform-independent foundation for worker credentials, normalized outcomes,
              guarantors, and trusted job completion.
            </p>
            <div className="mt-10 flex flex-wrap gap-3">
              <span className="border border-[#18211b]/20 bg-white/50 px-4 py-2 text-sm">Neon database</span>
              <span className="border border-[#18211b]/20 bg-white/50 px-4 py-2 text-sm">FastAPI</span>
              <span className="border border-[#18211b]/20 bg-white/50 px-4 py-2 text-sm">Next.js</span>
            </div>
          </div>

          <PortableRecord/>

          <aside className="border border-[#18211b]/15 bg-[#d8e3d5] p-7 shadow-[12px_12px_0_#18211b]">
            <div className="flex items-center justify-between border-b border-[#18211b]/15 pb-5">
              <span className="font-mono text-xs tracking-widest uppercase">System status</span>
              <span className="flex items-center gap-2 text-sm"><span className="h-2 w-2 rounded-full bg-[#3a8f63]" />Operational</span>
            </div>
            <dl className="mt-6 space-y-5">
              <div className="flex justify-between gap-4"><dt className="text-sm text-[#18211b]/60">API surface</dt><dd className="font-mono text-sm">/api/v1</dd></div>
              <div className="flex justify-between gap-4"><dt className="text-sm text-[#18211b]/60">Database</dt><dd className="font-mono text-sm">Neon / shared</dd></div>
              <div className="flex justify-between gap-4"><dt className="text-sm text-[#18211b]/60">Cache</dt><dd className="font-mono text-sm">Redis / local</dd></div>
            </dl>
            <div className="mt-8 border-t border-[#18211b]/15 pt-5 text-sm leading-6 text-[#18211b]/70">
              The scaffold is ready for the first vertical slice: outcome ingestion, normalization,
              and an explainable trust decision.
            </div>
          </aside>
        </section>

        <footer className="flex flex-col gap-2 border-t border-[#18211b]/15 pt-5 text-xs text-[#18211b]/55 sm:flex-row sm:justify-between">
          <span>Dynamic Trust Infrastructure</span>
          <span className="font-mono">BUILDING HISTORY -&gt; TRUSTED OUTCOMES</span>
        </footer>
      </div>
    </main>
  );
}
