"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  JobStatus,
  JobSummary,
  fetchJobs,
  uploadVideo,
  deleteJob,
} from "../lib/api";
import { Language, getCopy } from "../lib/i18n";

const MAX_FILE_SIZE_MB = 500;
const REFRESH_INTERVAL_MS = 10000;

type UploadState = "idle" | "uploading" | "success" | "error";

export type DashboardProps = {
  initialLanguage?: Language;
};

function formatDateTime(input: string, language: Language): string {
  const locale = language === "ja" ? "ja-JP" : "en-US";
  try {
    return new Intl.DateTimeFormat(locale, {
      dateStyle: "medium",
      timeStyle: "short",
    }).format(new Date(input));
  } catch {
    return input;
  }
}

function formatStageLabel(
  job: JobSummary,
  copy: ReturnType<typeof getCopy>,
): string {
  const label = copy.stageLabels[job.stage_key] ?? job.stage_key;
  return `${job.stage_index}/${job.stage_count} · ${label}`;
}

function formatStatus(
  status: JobStatus,
  language: Language,
): { label: string; description: string } {
  const copy = getCopy(language);
  return {
    label: copy.statusLabels[status] ?? status,
    description: copy.statusDescriptions[status] ?? "",
  };
}

export default function Dashboard({
  initialLanguage = "ja",
}: DashboardProps) {
  const [language, setLanguage] = useState<Language>(initialLanguage);
  const copy = useMemo(() => getCopy(language), [language]);

  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploadState, setUploadState] = useState<UploadState>("idle");
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadProgress, setUploadProgress] = useState<number>(0);
  const abortControllerRef = useRef<AbortController | null>(null);

  const [jobs, setJobs] = useState<JobSummary[]>([]);
  const [jobsError, setJobsError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [deletingJobId, setDeletingJobId] = useState<string | null>(null);
  const [notification, setNotification] = useState<string | null>(null);
  const [notificationType, setNotificationType] = useState<"success" | "error" | null>(null);

  const loadJobs = useCallback(async () => {
    try {
      const data = await fetchJobs();
      setJobs(data);
      setJobsError(null);
      setLastUpdated(new Date());
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "unknown error";
      setJobsError(message);
    }
  }, []);

  useEffect(() => {
    let active = true;
    const run = async () => {
      await loadJobs();
      if (!active) return;
      const id = window.setInterval(() => {
        loadJobs().catch(() => {
          /* errors handled in loadJobs */
        });
      }, REFRESH_INTERVAL_MS);
      return () => window.clearInterval(id);
    };

    let cleanup: (() => void) | undefined;
    run().then((fn) => {
      cleanup = fn;
    });

    return () => {
      active = false;
      if (cleanup) cleanup();
    };
  }, [loadJobs]);

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0] ?? null;
    setUploadError(null);
    setUploadState("idle");
    setUploadProgress(0);
    setSelectedFile(file);
  };

  const handleUpload = async () => {
    if (!selectedFile) {
      return;
    }

    const limitBytes = MAX_FILE_SIZE_MB * 1024 * 1024;
    if (selectedFile.size > limitBytes) {
      setUploadError(copy.uploadSizeError(MAX_FILE_SIZE_MB));
      setUploadState("error");
      return;
    }

    setUploadState("uploading");
    setUploadError(null);
    setUploadProgress(0);

    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      await uploadVideo(selectedFile, {
        signal: controller.signal,
        onProgress: (progress) => setUploadProgress(progress),
      });
      setUploadState("success");
      setSelectedFile(null);
      setUploadProgress(100);
      await loadJobs();
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "unknown error";
      setUploadError(copy.uploadError + message);
      setUploadState("error");
    } finally {
      abortControllerRef.current = null;
    }
  };

  const handleCancelUpload = () => {
    abortControllerRef.current?.abort();
    abortControllerRef.current = null;
  };

  const handleRefresh = () => {
    loadJobs().catch(() => {
      /* handled in loadJobs */
    });
  };

  const handleDeleteJob = async (jobId: string) => {
    if (!window.confirm(copy.deleteConfirm(jobId))) {
      return;
    }

    setDeletingJobId(jobId);
    setNotification(null);
    setNotificationType(null);

    try {
      await deleteJob(jobId);
      setNotification(copy.deleteSuccess);
      setNotificationType("success");
      await loadJobs();
    } catch (error) {
      const message = error instanceof Error ? error.message : "unknown error";
      setNotification(copy.deleteError + message);
      setNotificationType("error");
    } finally {
      setDeletingJobId(null);
    }
  };

  const renderLastUpdated = () => {
    if (!lastUpdated) return null;
    const timestamp = formatDateTime(lastUpdated.toISOString(), language);
    return (
      <p className="text-sm text-slate-400">
        {copy.lastUpdatedPrefix}: {timestamp}
      </p>
    );
  };

  return (
    <main className="flex min-h-screen flex-col gap-10 bg-slate-950 px-6 py-10 text-white sm:px-12 sm:py-16">
      <header className="mx-auto flex w-full max-w-6xl flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-col gap-2">
          <h1 className="text-3xl font-semibold sm:text-4xl">
            {copy.heroTitle}
          </h1>
          <p className="text-base text-slate-300 sm:text-lg">
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

      <section className="mx-auto w-full max-w-6xl rounded-3xl border border-slate-800 bg-slate-900/60 p-6 shadow-lg shadow-slate-950/40">
        <h2 className="text-xl font-semibold">{copy.uploadSectionTitle}</h2>
        <p className="mt-2 text-sm text-slate-300">{copy.uploadHelpText}</p>

        <div className="mt-4 flex flex-col gap-4 sm:flex-row sm:items-end">
          <label className="flex w-full flex-col gap-2 text-sm font-semibold text-slate-200 sm:w-auto">
            {copy.uploadSelectLabel}
            <input
              type="file"
              accept="video/mp4,video/quicktime,video/webm,audio/mpeg,audio/wav,audio/x-wav,audio/x-m4a,audio/aac,audio/flac,audio/ogg"
              onChange={handleFileChange}
              className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 file:mr-4 file:rounded-md file:border-0 file:bg-blue-600 file:px-4 file:py-2 file:font-semibold file:text-white hover:border-slate-500"
              aria-label={copy.uploadSelectPlaceholder}
            />
          </label>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={handleUpload}
              disabled={!selectedFile || uploadState === "uploading"}
              className="rounded-lg bg-blue-600 px-5 py-2 text-sm font-semibold text-white transition hover:bg-blue-500 disabled:cursor-not-allowed disabled:bg-slate-700"
            >
              {copy.uploadButton}
            </button>
            {uploadState === "uploading" && (
              <button
                type="button"
                onClick={handleCancelUpload}
                className="rounded-lg border border-red-400 px-4 py-2 text-sm font-semibold text-red-200 transition hover:border-red-300 hover:text-red-100"
              >
                Cancel
              </button>
            )}
          </div>
        </div>

        <div className="mt-4 min-h-[1.5rem] text-sm text-slate-200" aria-live="polite">
          {uploadState === "uploading" && (
            <div className="flex items-center gap-3">
              <div
                className="h-2 flex-1 overflow-hidden rounded-full bg-slate-800"
                role="progressbar"
                aria-valuemin={0}
                aria-valuenow={uploadProgress}
                aria-valuemax={100}
              >
                <div
                  className="h-full rounded-full bg-blue-500 transition-all"
                  style={{ width: `${uploadProgress}%` }}
                />
              </div>
              <span>{copy.uploadInProgress(uploadProgress)}</span>
            </div>
          )}
          {uploadState === "success" && (
            <span className="text-emerald-300">{copy.uploadSuccess}</span>
          )}
          {uploadState === "error" && uploadError && (
            <span className="text-red-300">{uploadError}</span>
          )}
        </div>
      </section>

      <section className="mx-auto flex w-full max-w-6xl flex-col gap-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="text-xl font-semibold">{copy.jobsSectionTitle}</h2>
            {renderLastUpdated()}
          </div>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={handleRefresh}
              className="rounded-lg border border-slate-700 px-4 py-2 text-sm font-semibold text-slate-200 transition hover:border-slate-500 hover:text-white"
            >
              {copy.refreshButton}
            </button>
          </div>
        </div>

        {notification ? (
          <p
            className={`rounded-lg border px-4 py-3 text-sm ${
              notificationType === "success"
                ? "border-emerald-400 bg-emerald-500/10 text-emerald-200"
                : "border-red-500 bg-red-500/10 text-red-200"
            }`}
          >
            {notification}
          </p>
        ) : null}

        {jobsError ? (
          <p className="rounded-lg border border-red-500 bg-red-500/10 px-4 py-3 text-sm text-red-200">
            {jobsError}
          </p>
        ) : null}

        {jobs.length === 0 ? (
          <p className="rounded-lg border border-slate-800 bg-slate-900/60 px-4 py-6 text-sm text-slate-300">
            {copy.jobsEmpty}
          </p>
        ) : (
          <div className="overflow-x-auto rounded-3xl border border-slate-800 bg-slate-900/60 shadow-lg shadow-slate-950/40">
            <table className="min-w-full divide-y divide-slate-800 text-sm">
              <thead className="bg-slate-900/80 uppercase tracking-wide text-slate-400">
                <tr>
                  <th className="px-4 py-3 text-left font-semibold">
                    {copy.jobsHeaders.jobId}
                  </th>
                  <th className="px-4 py-3 text-left font-semibold">
                    {copy.jobsHeaders.status}
                  </th>
                  <th className="px-4 py-3 text-left font-semibold">
                    {copy.jobsHeaders.progress}
                  </th>
                  <th className="px-4 py-3 text-left font-semibold">
                    {copy.jobsHeaders.updatedAt}
                  </th>
                  <th className="px-4 py-3 text-left font-semibold">
                    {copy.jobsHeaders.summary}
                  </th>
                  <th className="px-4 py-3 text-left font-semibold">
                    {copy.jobsHeaders.actions}
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {jobs.map((job) => {
                  const statusInfo = formatStatus(job.status, language);
                  return (
                    <tr key={job.job_id} className="hover:bg-slate-900/80">
                      <td className="px-4 py-3 font-mono text-slate-200">
                        {job.job_id}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex flex-col gap-1">
                          <span
                            className={`inline-flex w-fit rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-wide ${
                              job.status === "failed"
                                ? "bg-red-500/20 text-red-200"
                                : "bg-slate-800 text-slate-200"
                            }`}
                          >
                            {statusInfo.label}
                          </span>
                          {job.failure ? (
                            <>
                              <span
                                className="text-xs text-red-300"
                                data-testid="failure-stage"
                              >
                                {copy.failedAtStage(
                                  copy.stageLabels[job.failure.stage] ??
                                    job.failure.stage,
                                )}
                              </span>
                              <span
                                className="line-clamp-2 text-xs text-red-400/80"
                                data-testid="failure-message"
                              >
                                {job.failure.message}
                              </span>
                              <span
                                className="text-xs text-slate-500"
                                data-testid="failure-time"
                              >
                                {copy.failureOccurredAt(
                                  formatDateTime(
                                    job.failure.occurred_at,
                                    language,
                                  ),
                                )}
                              </span>
                            </>
                          ) : (
                            <span className="text-xs text-slate-400">
                              {statusInfo.description}
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="px-4 py-3 text-slate-200">
                        {formatStageLabel(job, copy)}
                      </td>
                      <td className="px-4 py-3 text-slate-200">
                        {formatDateTime(job.updated_at, language)}
                      </td>
                      <td className="px-4 py-3 text-slate-200">
                        {job.summary_count} / {job.action_item_count}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex flex-wrap gap-2">
                          <Link
                            href={`/meetings/${encodeURIComponent(job.job_id)}?lang=${language}`}
                            className="rounded-lg border border-blue-500 px-4 py-2 text-xs font-semibold text-blue-300 transition hover:bg-blue-500/10"
                          >
                            {copy.viewDetails}
                          </Link>
                          {job.can_delete && (
                            <button
                              type="button"
                              onClick={() => handleDeleteJob(job.job_id)}
                              disabled={deletingJobId === job.job_id}
                              className="rounded-lg border border-red-500 px-4 py-2 text-xs font-semibold text-red-300 transition hover:bg-red-500/10 disabled:cursor-not-allowed disabled:border-slate-700 disabled:text-slate-500"
                            >
                              {deletingJobId === job.job_id
                                ? copy.deleteInProgress
                                : copy.deleteButton}
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </main>
  );
}
