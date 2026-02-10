import type { JobSummary, MeetingDetail } from "../../src/lib/api";

export const JOBS_FIXTURE: JobSummary[] = [
  {
    job_id: "job-e2e-001",
    status: "completed",
    created_at: "2025-05-25T10:00:00Z",
    updated_at: "2025-05-25T11:00:00Z",
    progress: 1,
    stage_index: 4,
    stage_count: 4,
    stage_key: "summary",
    duration_ms: 120_000,
    languages: ["ja"],
    summary_count: 2,
    action_item_count: 1,
    can_delete: true,
  },
  {
    job_id: "job-e2e-002",
    status: "processing",
    created_at: "2025-05-25T12:00:00Z",
    updated_at: "2025-05-25T12:30:00Z",
    progress: 0.5,
    stage_index: 2,
    stage_count: 4,
    stage_key: "chunking",
    duration_ms: null,
    languages: [],
    summary_count: 0,
    action_item_count: 0,
    can_delete: false,
  },
];

export const FAILED_JOB: JobSummary = {
  job_id: "job-e2e-failed",
  status: "failed",
  created_at: "2025-05-25T14:00:00Z",
  updated_at: "2025-05-25T14:05:00Z",
  progress: 0.5,
  stage_index: 2,
  stage_count: 4,
  stage_key: "chunking",
  duration_ms: null,
  languages: [],
  summary_count: 0,
  action_item_count: 0,
  can_delete: false,
  failure: {
    stage: "chunking",
    message: "Failed to enqueue transcription job: Redis connection refused",
    occurred_at: "2025-05-25T14:05:00Z",
  },
};

export const FAILED_JOB_NO_DETAILS: JobSummary = {
  job_id: "job-e2e-failed-no-detail",
  status: "failed",
  created_at: "2025-05-25T15:00:00Z",
  updated_at: "2025-05-25T15:05:00Z",
  progress: 0.25,
  stage_index: 1,
  stage_count: 4,
  stage_key: "upload",
  duration_ms: null,
  languages: [],
  summary_count: 0,
  action_item_count: 0,
  can_delete: false,
};

export const JOBS_WITH_FAILURE: JobSummary[] = [
  ...JOBS_FIXTURE,
  FAILED_JOB,
];

export const EMPTY_JOBS: JobSummary[] = [];

export const MEETING_FIXTURE: MeetingDetail = {
  job_id: "job-e2e-001",
  summary_items: [
    {
      summary_id: "sum-1",
      job_id: "job-e2e-001",
      order: 0,
      segment_start_ms: 0,
      segment_end_ms: 60_000,
      summary_text: "会議のゴールを確認しました。",
      heading: "導入",
      priority: "高",
      highlights: ["ゴール共有"],
    },
  ],
  action_items: [
    {
      action_id: "act-1",
      job_id: "job-e2e-001",
      order: 0,
      description: "資料を共有する。",
      owner: "田中",
      due_date: "2025-05-30",
      segment_start_ms: 0,
      segment_end_ms: 60_000,
      priority: null,
    },
  ],
  segments: [
    {
      segment_id: "seg-1",
      job_id: "job-e2e-001",
      order: 0,
      start_ms: 0,
      end_ms: 60_000,
      text: "本日のアジェンダを確認します。",
      language: "ja",
      speaker_label: "司会",
    },
    {
      segment_id: "seg-2",
      job_id: "job-e2e-001",
      order: 1,
      start_ms: 60_000,
      end_ms: 120_000,
      text: "次のステップを議論しましょう。",
      language: "ja",
      speaker_label: "参加者A",
    },
  ],
  quality_metrics: {
    coverage_ratio: 0.9,
  },
};
