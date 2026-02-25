"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import {
  JobDetail,
  MeetingDetail,
  SpeakerMappings,
  SpeakerProfile,
  fetchJob,
  fetchMeeting,
  fetchMeetingMarkdown,
  updateJobTitle,
  updateSpeakerMappings,
} from "../lib/api";
import { Language, getCopy } from "../lib/i18n";
import { getOrgColor, getSpeakerColor } from "../lib/speaker-colors";

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

function generateProfileId(): string {
  return Math.random().toString(36).slice(2, 8);
}

type DraftRow = {
  label: string;
  profileId: string;
  name: string;
  organization: string;
};

function buildDraftRows(
  uniqueLabels: string[],
  mappings: SpeakerMappings | null | undefined,
): DraftRow[] {
  return uniqueLabels.map((label) => {
    if (mappings) {
      const pid = mappings.label_to_profile[label];
      if (pid) {
        const profile = mappings.profiles[pid];
        if (profile) {
          return {
            label,
            profileId: pid,
            name: profile.name,
            organization: profile.organization,
          };
        }
      }
    }
    return {
      label,
      profileId: generateProfileId(),
      name: "",
      organization: "",
    };
  });
}

function draftRowsToMappings(rows: DraftRow[]): SpeakerMappings {
  const profiles: Record<string, SpeakerProfile> = {};
  const label_to_profile: Record<string, string> = {};

  // Pass 1: collect profiles that have a name (merged rows share a profileId,
  // so only one row needs to carry the name for the profile to be valid)
  for (const row of rows) {
    if (row.name.trim()) {
      profiles[row.profileId] = {
        profile_id: row.profileId,
        name: row.name.trim(),
        organization: row.organization.trim(),
      };
    }
  }

  // Pass 2: map every label whose profileId was collected above
  for (const row of rows) {
    if (row.profileId in profiles) {
      label_to_profile[row.label] = row.profileId;
    }
  }

  return { profiles, label_to_profile };
}

function resolveSpeakerLabel(
  label: string,
  mappings: SpeakerMappings | null | undefined,
): { displayName: string; organization: string } | null {
  if (!mappings) return null;
  const pid = mappings.label_to_profile[label];
  if (!pid) return null;
  const profile = mappings.profiles[pid];
  if (!profile) return null;
  return { displayName: profile.name, organization: profile.organization };
}

export function MeetingDetailView({
  jobId,
  initialLanguage = "ja",
  onLanguageChange,
}: MeetingDetailViewProps) {
  const [language, setLanguage] = useState<Language>(initialLanguage);
  const copy = useMemo(() => getCopy(language), [language]);

  const [data, setData] = useState<MeetingDetail | null>(null);
  const [jobDetail, setJobDetail] = useState<JobDetail | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<string>("");
  const [editingTitle, setEditingTitle] = useState(false);
  const [editingTitleValue, setEditingTitleValue] = useState("");
  const [savingTitle, setSavingTitle] = useState(false);
  const [titleNotification, setTitleNotification] = useState<string | null>(null);
  const [titleNotificationType, setTitleNotificationType] = useState<"success" | "error" | null>(null);

  // Speaker profile editing state
  const [draftRows, setDraftRows] = useState<DraftRow[]>([]);
  const [mergeSources, setMergeSources] = useState<Set<string>>(new Set());
  const [savingSpeakers, setSavingSpeakers] = useState(false);
  const [speakerNotification, setSpeakerNotification] = useState<string | null>(null);
  const [speakerNotificationType, setSpeakerNotificationType] = useState<"success" | "error" | null>(null);

  useEffect(() => {
    setLanguage(initialLanguage);
  }, [initialLanguage]);

  const uniqueLabels = useMemo(() => {
    if (!data) return [];
    const labels = new Set<string>();
    for (const seg of data.segments) {
      if (seg.speaker_label) {
        labels.add(seg.speaker_label);
      }
    }
    return Array.from(labels).sort();
  }, [data]);

  useEffect(() => {
    let active = true;
    setIsLoading(true);
    setError(null);

    Promise.all([fetchMeeting(jobId), fetchJob(jobId)])
      .then(([meetingDetail, job]) => {
        if (!active) return;
        setData(meetingDetail);
        setJobDetail(job);
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

  // Initialize draft rows when data loads or unique labels change
  useEffect(() => {
    if (!data) return;
    setDraftRows(buildDraftRows(uniqueLabels, data.speaker_mappings));
  }, [data, uniqueLabels]);

  useEffect(() => {
    onLanguageChange?.(language);
  }, [language, onLanguageChange]);

  const filteredSegments = useMemo(
    () => filterSegments(data, filter),
    [data, filter],
  );

  const handleTitleClick = () => {
    setEditingTitle(true);
    setEditingTitleValue(jobDetail?.title ?? "");
  };

  const handleTitleSave = async (value: string) => {
    const trimmed = value.trim();
    if (!trimmed) {
      setEditingTitle(false);
      return;
    }

    setSavingTitle(true);
    try {
      const updated = await updateJobTitle(jobId, trimmed);
      setJobDetail(updated);
      setTitleNotification(copy.titleSaveSuccess);
      setTitleNotificationType("success");
    } catch (err) {
      const message = err instanceof Error ? err.message : "unknown error";
      setTitleNotification(copy.titleSaveError + message);
      setTitleNotificationType("error");
    } finally {
      setSavingTitle(false);
      setEditingTitle(false);
    }
  };

  const handleTitleKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Enter") {
      event.preventDefault();
      const value = editingTitleValue;
      setEditingTitle(false);
      handleTitleSave(value);
    } else if (event.key === "Escape") {
      setEditingTitle(false);
    }
  };

  const handleTitleBlur = () => {
    if (!editingTitle) return;
    const value = editingTitleValue;
    setEditingTitle(false);
    handleTitleSave(value);
  };

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

  const handleExportMarkdown = useCallback(async () => {
    const blob = await fetchMeetingMarkdown(jobId);
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${jobId}.md`;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
  }, [jobId]);

  // Speaker profile handlers
  const handleDraftChange = (label: string, field: "name" | "organization", value: string) => {
    setDraftRows((prev) =>
      prev.map((row) => (row.label === label ? { ...row, [field]: value } : row)),
    );
  };

  const handleMerge = (targetLabel: string) => {
    if (mergeSources.size === 0) return;
    setDraftRows((prev) => {
      const targetRow = prev.find((r) => r.label === targetLabel);
      if (!targetRow) return prev;
      return prev.map((row) => {
        if (mergeSources.has(row.label)) {
          return { ...row, profileId: targetRow.profileId };
        }
        return row;
      });
    });
    setMergeSources(new Set());
  };

  const handleUnmerge = (label: string) => {
    setDraftRows((prev) =>
      prev.map((row) =>
        row.label === label ? { ...row, profileId: generateProfileId() } : row,
      ),
    );
  };

  const handleSpeakerSave = async () => {
    setSavingSpeakers(true);
    setSpeakerNotification(null);
    try {
      const mappings = draftRowsToMappings(draftRows);
      const saved = await updateSpeakerMappings(jobId, mappings);
      setData((prev) => (prev ? { ...prev, speaker_mappings: saved } : prev));
      setSpeakerNotification(copy.speakerSaveSuccess);
      setSpeakerNotificationType("success");
    } catch (err) {
      const message = err instanceof Error ? err.message : "unknown error";
      setSpeakerNotification(copy.speakerSaveError + message);
      setSpeakerNotificationType("error");
    } finally {
      setSavingSpeakers(false);
    }
  };

  const handleSpeakerReset = () => {
    if (!data) return;
    setDraftRows(buildDraftRows(uniqueLabels, data.speaker_mappings));
    setMergeSources(new Set());
    setSpeakerNotification(null);
  };

  const toggleMergeSource = (label: string) => {
    setMergeSources((prev) => {
      const next = new Set(prev);
      if (next.has(label)) {
        next.delete(label);
      } else {
        next.add(label);
      }
      return next;
    });
  };

  // Compute merged groups for display
  const mergedGroups = useMemo(() => {
    const groups = new Map<string, string[]>();
    for (const row of draftRows) {
      const existing = groups.get(row.profileId) ?? [];
      existing.push(row.label);
      groups.set(row.profileId, existing);
    }
    return groups;
  }, [draftRows]);

  return (
    <main className="flex min-h-screen flex-col gap-10 bg-slate-950 px-6 py-10 text-white sm:px-12 sm:py-16">
      <header className="mx-auto flex w-full max-w-6xl flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-col gap-2">
          <h1 className="text-3xl font-semibold sm:text-4xl">
            {copy.meetingTitlePrefix} · {jobId}
          </h1>
          <div className="mt-1">
            {editingTitle ? (
              <input
                type="text"
                value={editingTitleValue}
                onChange={(e) => setEditingTitleValue(e.target.value)}
                onKeyDown={handleTitleKeyDown}
                onBlur={handleTitleBlur}
                placeholder={copy.titlePlaceholder}
                disabled={savingTitle}
                autoFocus
                className="w-full max-w-md rounded border border-slate-600 bg-slate-950 px-3 py-1.5 text-base text-slate-100 placeholder:text-slate-500 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                aria-label={copy.titleEditLabel}
                data-testid="detail-title-input"
              />
            ) : (
              <button
                type="button"
                onClick={handleTitleClick}
                className="cursor-pointer rounded px-3 py-1.5 text-left text-base transition hover:bg-slate-800"
                title={copy.titleEditLabel}
                data-testid="detail-title-display"
              >
                {jobDetail?.title ? (
                  <span className="text-slate-200">{jobDetail.title}</span>
                ) : (
                  <span className="italic text-slate-500">
                    {copy.titlePlaceholder}
                  </span>
                )}
              </button>
            )}
            {titleNotification && (
              <p
                className={`mt-1 text-xs ${
                  titleNotificationType === "success"
                    ? "text-emerald-300"
                    : "text-red-300"
                }`}
              >
                {titleNotification}
              </p>
            )}
          </div>
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
          <div className="flex gap-2">
            <button
              type="button"
              onClick={handleExport}
              disabled={!data}
              className="w-fit rounded-lg border border-blue-500 px-4 py-2 text-xs font-semibold text-blue-300 transition hover:bg-blue-500/10 disabled:cursor-not-allowed disabled:border-slate-700 disabled:text-slate-500"
            >
              {copy.meetingExportButton}
            </button>
            <button
              type="button"
              onClick={handleExportMarkdown}
              disabled={!data}
              className="w-fit rounded-lg border border-emerald-500 px-4 py-2 text-xs font-semibold text-emerald-300 transition hover:bg-emerald-500/10 disabled:cursor-not-allowed disabled:border-slate-700 disabled:text-slate-500"
            >
              {copy.meetingExportMarkdownButton}
            </button>
          </div>
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
              <details className="group">
                <summary className="cursor-pointer list-none [&::-webkit-details-marker]:hidden text-xl font-semibold flex items-center gap-2">
                  <span className="transition-transform group-open:rotate-90">▶</span>
                  <span>{copy.meetingSummaryHeading}</span>
                  <span className="text-sm font-normal text-slate-400">({data.summary_items.length})</span>
                </summary>
                {data.summary_items.length === 0 ? (
                  <p className="mt-3 text-sm text-slate-400">
                    {copy.meetingEmptySummary}
                  </p>
                ) : (
                  <ul className="mt-4 space-y-4">
                    {data.summary_items.map((item) => (
                      <li
                        key={item.summary_id}
                        className="rounded-2xl border border-slate-800 bg-slate-900/80"
                      >
                        <details className="group/item">
                          <summary className="cursor-pointer list-none [&::-webkit-details-marker]:hidden p-4 flex items-center gap-2 text-xs text-slate-400">
                            <span className="transition-transform group-open/item:rotate-90">▶</span>
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
                          </summary>
                          <div className="px-4 pb-4">
                            <p className="text-sm text-slate-100">
                              {item.summary_text}
                            </p>
                            {item.highlights.length > 0 && (
                              <ul className="mt-2 space-y-1 text-xs text-slate-300">
                                {item.highlights.map((highlight) => (
                                  <li key={highlight}>• {highlight}</li>
                                ))}
                              </ul>
                            )}
                          </div>
                        </details>
                      </li>
                    ))}
                  </ul>
                )}
              </details>

              <details className="group">
                <summary className="cursor-pointer list-none [&::-webkit-details-marker]:hidden text-xl font-semibold flex items-center gap-2">
                  <span className="transition-transform group-open:rotate-90">▶</span>
                  <span>{copy.meetingActionHeading}</span>
                  <span className="text-sm font-normal text-slate-400">({data.action_items.length})</span>
                </summary>
                {data.action_items.length === 0 ? (
                  <p className="mt-3 text-sm text-slate-400">
                    {copy.meetingEmptyAction}
                  </p>
                ) : (
                  <ul className="mt-4 space-y-4">
                    {data.action_items.map((item, index) => (
                      <li
                        key={item.action_id}
                        className="rounded-2xl border border-slate-800 bg-slate-900/80 p-4"
                      >
                        <p className="text-sm text-slate-100">
                          <span className="font-semibold text-blue-300 mr-2">#{index + 1}</span>
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
              </details>

              {/* Speaker Profiles Section */}
              {uniqueLabels.length > 0 && (
                <details className="group" data-testid="speaker-profiles-section">
                  <summary className="cursor-pointer list-none [&::-webkit-details-marker]:hidden text-xl font-semibold flex items-center gap-2">
                    <span className="transition-transform group-open:rotate-90">▶</span>
                    <span>{copy.speakerHeading}</span>
                    <span className="text-sm font-normal text-slate-400">({uniqueLabels.length})</span>
                  </summary>
                  <div className="mt-4 overflow-x-auto">
                    <div className="mb-3 flex items-center gap-3">
                      <button
                        type="button"
                        onClick={handleSpeakerSave}
                        disabled={savingSpeakers}
                        className="rounded-lg border border-blue-500 px-4 py-2 text-xs font-semibold text-blue-300 transition hover:bg-blue-500/10 disabled:cursor-not-allowed disabled:border-slate-700 disabled:text-slate-500"
                        data-testid="speaker-save-top"
                      >
                        {copy.speakerSave}
                      </button>
                      <button
                        type="button"
                        onClick={handleSpeakerReset}
                        className="rounded-lg border border-slate-600 px-4 py-2 text-xs font-semibold text-slate-300 transition hover:border-slate-400"
                        data-testid="speaker-reset-top"
                      >
                        {copy.speakerReset}
                      </button>
                      {speakerNotification && (
                        <p
                          className={`text-xs ${
                            speakerNotificationType === "success"
                              ? "text-emerald-300"
                              : "text-red-300"
                          }`}
                        >
                          {speakerNotification}
                        </p>
                      )}
                    </div>
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-slate-700 text-left text-xs text-slate-400">
                          <th className="pb-2 pr-3">{copy.speakerLabelColumn}</th>
                          <th className="pb-2 pr-3">{copy.speakerNameColumn}</th>
                          <th className="pb-2 pr-3">{copy.speakerOrgColumn}</th>
                          <th className="pb-2">{copy.speakerActionsColumn}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {draftRows.map((row) => {
                          const groupLabels = mergedGroups.get(row.profileId) ?? [];
                          const isMerged = groupLabels.length > 1;
                          const otherLabels = groupLabels.filter((l) => l !== row.label);

                          return (
                            <tr key={row.label} className="border-b border-slate-800">
                              <td className="py-2 pr-3">
                                <span className="font-mono text-xs text-slate-300">{row.label}</span>
                                {isMerged && otherLabels.length > 0 && (
                                  <span className="ml-2 text-xs text-slate-500">
                                    {copy.speakerMergedFrom(otherLabels.join(", "))}
                                  </span>
                                )}
                              </td>
                              <td className="py-2 pr-3">
                                <input
                                  type="text"
                                  value={row.name}
                                  onChange={(e) => handleDraftChange(row.label, "name", e.target.value)}
                                  placeholder={copy.speakerNamePlaceholder}
                                  className="w-full rounded border border-slate-700 bg-slate-950 px-2 py-1 text-sm text-slate-100 placeholder:text-slate-600 focus:border-blue-500 focus:outline-none"
                                  data-testid={`speaker-name-${row.label}`}
                                />
                              </td>
                              <td className="py-2 pr-3">
                                <input
                                  type="text"
                                  value={row.organization}
                                  onChange={(e) => handleDraftChange(row.label, "organization", e.target.value)}
                                  placeholder={copy.speakerOrgPlaceholder}
                                  className="w-full rounded border border-slate-700 bg-slate-950 px-2 py-1 text-sm text-slate-100 placeholder:text-slate-600 focus:border-blue-500 focus:outline-none"
                                  data-testid={`speaker-org-${row.label}`}
                                />
                              </td>
                              <td className="py-2">
                                <div className="flex items-center gap-2">
                                  {isMerged ? (
                                    <button
                                      type="button"
                                      onClick={() => handleUnmerge(row.label)}
                                      className="rounded border border-amber-600 px-2 py-1 text-xs text-amber-300 transition hover:bg-amber-600/20"
                                      data-testid={`speaker-unmerge-${row.label}`}
                                    >
                                      {copy.speakerUnmerge}
                                    </button>
                                  ) : (
                                    <>
                                      <label className="flex items-center gap-1 text-xs text-slate-400">
                                        <input
                                          type="checkbox"
                                          checked={mergeSources.has(row.label)}
                                          onChange={() => toggleMergeSource(row.label)}
                                          className="rounded"
                                          data-testid={`speaker-merge-check-${row.label}`}
                                        />
                                        {copy.speakerSelectMergeSource}
                                      </label>
                                      {mergeSources.size > 0 && !mergeSources.has(row.label) && (
                                        <button
                                          type="button"
                                          onClick={() => handleMerge(row.label)}
                                          className="rounded border border-blue-600 px-2 py-1 text-xs text-blue-300 transition hover:bg-blue-600/20"
                                          data-testid={`speaker-merge-into-${row.label}`}
                                        >
                                          {copy.speakerMergeInto}
                                        </button>
                                      )}
                                    </>
                                  )}
                                </div>
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                    <div className="mt-4 flex items-center gap-3">
                      <button
                        type="button"
                        onClick={handleSpeakerSave}
                        disabled={savingSpeakers}
                        className="rounded-lg border border-blue-500 px-4 py-2 text-xs font-semibold text-blue-300 transition hover:bg-blue-500/10 disabled:cursor-not-allowed disabled:border-slate-700 disabled:text-slate-500"
                        data-testid="speaker-save"
                      >
                        {copy.speakerSave}
                      </button>
                      <button
                        type="button"
                        onClick={handleSpeakerReset}
                        className="rounded-lg border border-slate-600 px-4 py-2 text-xs font-semibold text-slate-300 transition hover:border-slate-400"
                        data-testid="speaker-reset"
                      >
                        {copy.speakerReset}
                      </button>
                      {speakerNotification && (
                        <p
                          className={`text-xs ${
                            speakerNotificationType === "success"
                              ? "text-emerald-300"
                              : "text-red-300"
                          }`}
                        >
                          {speakerNotification}
                        </p>
                      )}
                    </div>
                  </div>
                </details>
              )}

              <details className="group">
                <summary className="cursor-pointer list-none [&::-webkit-details-marker]:hidden text-xl font-semibold flex items-center gap-2">
                  <span className="transition-transform group-open:rotate-90">▶</span>
                  <span>{copy.meetingTranscriptHeading}</span>
                  <span className="text-sm font-normal text-slate-400">({data.segments.length})</span>
                </summary>
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
                  <div className="mt-4 rounded-2xl border border-slate-800 bg-slate-900/80 p-6 text-sm leading-relaxed text-slate-100">
                    {filteredSegments.map((segment, index) => {
                      const resolved = segment.speaker_label
                        ? resolveSpeakerLabel(segment.speaker_label, data.speaker_mappings)
                        : null;
                      const speakerDisplay = resolved
                        ? resolved.displayName
                        : segment.speaker_label;
                      const colorClass = resolved
                        ? getOrgColor(resolved.organization)
                        : getSpeakerColor(segment.speaker_label ?? "");

                      return (
                        <p key={segment.segment_id} className={index > 0 ? "mt-3" : ""}>
                          <span className="mr-1 font-mono text-xs font-semibold text-blue-300">
                            [{formatTimestamp(segment.start_ms)}]
                          </span>
                          {speakerDisplay && (
                            <span className={`mr-1 text-xs font-semibold ${colorClass}`}>
                              {speakerDisplay}:
                            </span>
                          )}
                          <span className={`whitespace-pre-wrap ${colorClass}`}>{segment.text}</span>
                        </p>
                      );
                    })}
                  </div>
                )}
              </details>

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
