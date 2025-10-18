"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import {
  MeetingDetail,
  fetchMeeting,
} from "../lib/api";
import { Language, getCopy } from "../lib/i18n";

type MeetingDetailViewProps = {
  jobId: string;
  initialLanguage?: Language;
  onLanguageChange?: (language: Language) => void;
};

function formatTimestamp(ms: number): string {
  const totalSeconds = Math.floor(ms / 1000);
  const minutes = Math.floor(totalSeconds / 60)
    .toString()
    .padStart(2, "0");
  const seconds = (totalSeconds % 60).toString().padStart(2, "0");
  return `${minutes}:${seconds}`;
}

function filterSegments(detail: MeetingDetail | null, term: string) {
  if (!detail) return [];
  if (!term.trim()) return detail.segments;
  const lower = term.toLowerCase();
  return detail.segments.filter((segment) =>
    segment.text.toLowerCase().includes(lower),
  );
}

export function MeetingDetailView({
  jobId,
  initialLanguage = "ja",
  onLanguageChange,
}: MeetingDetailViewProps) {
  const [language, setLanguage] = useState<Language>(initialLanguage);
  const copy = useMemo(() => getCopy(language), [language]);

  const [data, setData] = useState<MeetingDetail | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<string>("");

  useEffect(() => {
    setLanguage(initialLanguage);
  }, [initialLanguage]);

  useEffect(() => {
    let active = true;
    setIsLoading(true);
    setError(null);

    fetchMeeting(jobId)
      .then((detail) => {
        if (!active) return;
        setData(detail);
        setIsLoading(false);
      })
      .catch((err) => {
        if (!active) return;
        setError(err instanceof Error ? err.message : "unknown error");
        setIsLoading(false);
      });

    return () => {
      active = false;
    };
  }, [jobId]);

  useEffect(() => {
    onLanguageChange?.(language);
  }, [language, onLanguageChange]);

  const filteredSegments = useMemo(
    () => filterSegments(data, filter),
    [data, filter],
  );

  const handleExport = useCallback(() => {
    if (!data) return;
    const blob = new Blob([JSON.stringify(data, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${jobId}.json`;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
  }, [data, jobId]);

  return (
    <main className="flex min-h-screen flex-col gap-10 bg-slate-950 px-6 py-10 text-white sm:px-12 sm:py-16">
      <header className="mx-auto flex w-full max-w-6xl flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-col gap-2">
          <h1 className="text-3xl font-semibold sm:text-4xl">
            {copy.meetingTitlePrefix} · {jobId}
          </h1>
          <p className="text-sm text-slate-300">
            {copy.heroSubtitle}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {(["ja", "en"] as Language[]).map((option) => (
            <button
              key={option}
              type="button"
              onClick={() => setLanguage(option)}
              className={`rounded-full border px-4 py-2 text-sm font-semibold transition ${
                language === option
                  ? "border-blue-500 bg-blue-600 text-white"
                  : "border-slate-600 bg-slate-900 text-slate-200 hover:border-slate-400"
              }`}
              aria-pressed={language === option}
            >
              {copy.languageNames[option]}
            </button>
          ))}
        </div>
      </header>

      <section className="mx-auto flex w-full max-w-6xl flex-col gap-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <Link
            href={`/?lang=${language}`}
            className="w-fit rounded-lg border border-slate-700 px-4 py-2 text-xs font-semibold text-slate-200 transition hover:border-slate-500 hover:text-white"
          >
            {copy.meetingBackLink}
          </Link>
          <button
            type="button"
            onClick={handleExport}
            disabled={!data}
            className="w-fit rounded-lg border border-blue-500 px-4 py-2 text-xs font-semibold text-blue-300 transition hover:bg-blue-500/10 disabled:cursor-not-allowed disabled:border-slate-700 disabled:text-slate-500"
          >
            {copy.meetingExportButton}
          </button>
        </div>

        <div className="rounded-3xl border border-slate-800 bg-slate-900/60 p-6 shadow-lg shadow-slate-950/40">
          {isLoading && (
            <p className="text-sm text-slate-300">{copy.meetingLoading}</p>
          )}
          {error && (
            <p className="text-sm text-red-300">{copy.meetingError}</p>
          )}
          {!isLoading && !error && data && (
            <div className="flex flex-col gap-8">
              <section>
                <h2 className="text-xl font-semibold">
                  {copy.meetingSummaryHeading}
                </h2>
                {data.summary_items.length === 0 ? (
                  <p className="mt-3 text-sm text-slate-400">
                    {copy.meetingEmptySummary}
                  </p>
                ) : (
                  <ul className="mt-4 space-y-4">
                    {data.summary_items.map((item) => (
                      <li
                        key={item.summary_id}
                        className="rounded-2xl border border-slate-800 bg-slate-900/80 p-4"
                      >
                        <div className="flex flex-wrap items-center gap-2 text-xs text-slate-400">
                          <span className="font-mono">
                            {formatTimestamp(item.segment_start_ms)} -{" "}
                            {formatTimestamp(item.segment_end_ms)}
                          </span>
                          {item.heading && (
                            <span className="rounded-full bg-blue-500/20 px-2 py-1 font-semibold text-blue-200">
                              {item.heading}
                            </span>
                          )}
                          {item.priority && (
                            <span className="rounded-full bg-amber-500/20 px-2 py-1 font-semibold text-amber-200">
                              {item.priority}
                            </span>
                          )}
                        </div>
                        <p className="mt-2 text-sm text-slate-100">
                          {item.summary_text}
                        </p>
                        {item.highlights.length > 0 && (
                          <ul className="mt-2 space-y-1 text-xs text-slate-300">
                            {item.highlights.map((highlight) => (
                              <li key={highlight}>• {highlight}</li>
                            ))}
                          </ul>
                        )}
                      </li>
                    ))}
                  </ul>
                )}
              </section>

              <section>
                <h2 className="text-xl font-semibold">
                  {copy.meetingActionHeading}
                </h2>
                {data.action_items.length === 0 ? (
                  <p className="mt-3 text-sm text-slate-400">
                    {copy.meetingEmptyAction}
                  </p>
                ) : (
                  <ul className="mt-4 space-y-4">
                    {data.action_items.map((item) => (
                      <li
                        key={item.action_id}
                        className="rounded-2xl border border-slate-800 bg-slate-900/80 p-4"
                      >
                        <p className="text-sm text-slate-100">
                          {item.description}
                        </p>
                        <div className="mt-2 flex flex-wrap gap-3 text-xs text-slate-400">
                          {item.owner && (
                            <span>
                              Owner:{" "}
                              <span className="font-semibold text-slate-200">
                                {item.owner}
                              </span>
                            </span>
                          )}
                          {item.due_date && (
                            <span>
                              Due:{" "}
                              <span className="font-semibold text-slate-200">
                                {item.due_date}
                              </span>
                            </span>
                          )}
                          {item.segment_start_ms != null && (
                            <span className="font-mono text-slate-300">
                              {formatTimestamp(item.segment_start_ms)}-
                              {item.segment_end_ms
                                ? formatTimestamp(item.segment_end_ms)
                                : ""}
                            </span>
                          )}
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </section>

              <section>
                <h2 className="text-xl font-semibold">
                  {copy.meetingTranscriptHeading}
                </h2>
                <div className="mt-3">
                  <label className="text-xs text-slate-300">
                    <span className="sr-only">Search transcript</span>
                    <input
                      type="search"
                      value={filter}
                      onChange={(event) => setFilter(event.target.value)}
                      placeholder={copy.meetingSearchPlaceholder}
                      className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-500 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                    />
                  </label>
                </div>
                {filteredSegments.length === 0 ? (
                  <p className="mt-3 text-sm text-slate-400">
                    {copy.meetingEmptyTranscript}
                  </p>
                ) : (
                  <ul className="mt-4 space-y-3">
                    {filteredSegments.map((segment) => (
                      <li
                        key={segment.segment_id}
                        className="rounded-2xl border border-slate-800 bg-slate-900/80 p-4 text-sm text-slate-100"
                      >
                        <span className="font-mono text-xs text-blue-300">
                          {formatTimestamp(segment.start_ms)}-
                          {formatTimestamp(segment.end_ms)}
                        </span>
                        <p className="mt-2 whitespace-pre-wrap leading-relaxed">
                          {segment.text}
                        </p>
                      </li>
                    ))}
                  </ul>
                )}
              </section>

              {data.quality_metrics && (
                <section className="rounded-2xl border border-slate-800 bg-slate-900/80 p-4 text-sm text-slate-200">
                  <h2 className="text-base font-semibold text-slate-100">
                    Quality Metrics
                  </h2>
                  <dl className="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-2">
                    {Object.entries(data.quality_metrics).map(([key, value]) => (
                      <div key={key} className="flex flex-col">
                        <dt className="text-xs uppercase tracking-wide text-slate-400">
                          {key}
                        </dt>
                        <dd className="text-sm text-slate-200">{String(value)}</dd>
                      </div>
                    ))}
                  </dl>
                </section>
              )}
            </div>
          )}
        </div>
      </section>
    </main>
  );
}
