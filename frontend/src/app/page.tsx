export default function Home() {
  return (
    <main className="flex min-h-screen flex-col gap-12 bg-slate-950 px-8 py-16 text-white sm:px-16">
      <section className="mx-auto flex w-full max-w-4xl flex-col items-center text-center sm:items-start sm:text-left">
        <span className="rounded-full bg-slate-800 px-4 py-1 text-sm font-semibold uppercase tracking-wide text-slate-300">
          AI-Powered Meeting Productivity
        </span>
        <h1 className="mt-6 text-balance text-4xl font-bold leading-tight sm:text-5xl">
          MeetingAI Minutes Generator
        </h1>
        <p className="mt-4 text-lg text-slate-200 sm:text-xl">
          Upload your meeting recordings and receive accurate transcripts,
          timestamped summaries, and action items in minutes.
        </p>
        <div className="mt-8 flex flex-col items-center gap-4 sm:flex-row">
          <button className="rounded-full bg-blue-500 px-6 py-3 text-base font-semibold text-white transition hover:bg-blue-600">
            Upload Recording
          </button>
          <button className="rounded-full border border-slate-500 px-6 py-3 text-base font-semibold text-slate-100 transition hover:border-slate-300 hover:text-white">
            View Sample Report
          </button>
        </div>
      </section>

      <section className="mx-auto grid w-full max-w-5xl gap-6 sm:grid-cols-3">
        <FeatureCard
          title="Accurate Transcripts"
          description="Process audio with GPT-4o Transcribe and keep speaker-aware, timestamped text."
        />
        <FeatureCard
          title="Actionable Summaries"
          description="Highlight key decisions, risks, and follow-ups tailored for busy teams."
        />
        <FeatureCard
          title="Secure Workflow"
          description="Data encrypted in transit and at rest, with configurable retention policies."
        />
      </section>
    </main>
  );
}

type FeatureCardProps = {
  title: string;
  description: string;
};

function FeatureCard({ title, description }: FeatureCardProps) {
  return (
    <article className="flex flex-col gap-2 rounded-3xl border border-slate-800 bg-slate-900/60 p-6 shadow-lg shadow-slate-950/40 transition hover:border-blue-500/60">
      <h2 className="text-xl font-semibold text-white">{title}</h2>
      <p className="text-sm text-slate-300">{description}</p>
    </article>
  );
}
