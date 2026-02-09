export type JobStatus = "pending" | "processing" | "completed" | "failed";

const API_BASE =
  process.env.NEXT_PUBLIC_BACKEND_URL?.replace(/\/$/, "") ??
  "http://localhost:8000";

async function requestJson<T>(input: RequestInfo, init?: RequestInit): Promise<T> {
  const response = await fetch(input, init);
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed with status ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export interface JobSummary {
  job_id: string;
  status: JobStatus;
  created_at: string;
  updated_at: string;
  progress: number;
  duration_ms?: number | null;
  languages: string[];
  summary_count: number;
  action_item_count: number;
  stage_index: number;
  stage_count: number;
  stage_key: string;
  can_delete: boolean;
}

export interface JobDetail extends JobSummary {
  quality_metrics?: Record<string, unknown> | null;
}

export interface UploadResponse {
  job_id: string;
}

export interface SummaryItem {
  summary_id: string;
  job_id: string;
  order: number;
  segment_start_ms: number;
  segment_end_ms: number;
  summary_text: string;
  heading?: string | null;
  priority?: string | null;
  highlights: string[];
}

export interface ActionItem {
  action_id: string;
  job_id: string;
  order: number;
  description: string;
  owner?: string | null;
  due_date?: string | null;
  segment_start_ms?: number | null;
  segment_end_ms?: number | null;
  priority?: string | null;
}

export interface TranscriptSegment {
  segment_id: string;
  job_id: string;
  order: number;
  start_ms: number;
  end_ms: number;
  text: string;
  language?: string | null;
  speaker_label?: string | null;
}

export interface MeetingDetail {
  job_id: string;
  summary_items: SummaryItem[];
  action_items: ActionItem[];
  segments: TranscriptSegment[];
  quality_metrics?: Record<string, unknown> | null;
}

export async function fetchJobs(): Promise<JobSummary[]> {
  return requestJson<JobSummary[]>(`${API_BASE}/api/jobs`);
}

export async function fetchJob(jobId: string): Promise<JobDetail> {
  return requestJson<JobDetail>(`${API_BASE}/api/jobs/${encodeURIComponent(jobId)}`);
}

export async function fetchMeeting(jobId: string): Promise<MeetingDetail> {
  return requestJson<MeetingDetail>(
    `${API_BASE}/api/meetings/${encodeURIComponent(jobId)}`,
  );
}

export async function deleteJob(jobId: string): Promise<void> {
  const response = await fetch(
    `${API_BASE}/api/jobs/${encodeURIComponent(jobId)}`,
    { method: "DELETE" },
  );
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Delete failed with status ${response.status}`);
  }
}

type UploadOptions = {
  onProgress?: (percentage: number) => void;
  signal?: AbortSignal;
};

export function uploadVideo(
  file: File,
  options: UploadOptions = {},
): Promise<UploadResponse> {
  const { onProgress, signal } = options;

  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const formData = new FormData();
    formData.append("file", file);

    xhr.open("POST", `${API_BASE}/api/videos`, true);

    const abortHandler = () => {
      xhr.abort();
      reject(new DOMException("Upload aborted", "AbortError"));
    };

    if (signal) {
      if (signal.aborted) {
        abortHandler();
        return;
      }
      signal.addEventListener("abort", abortHandler);
    }

    xhr.upload.onprogress = (event) => {
      if (!onProgress || event.lengthComputable === false) {
        return;
      }
      const progress = Math.round((event.loaded / event.total) * 100);
      onProgress(progress);
    };

    xhr.onerror = () => {
      reject(new Error("Network error while uploading file"));
    };

    xhr.onload = () => {
      if (signal) {
        signal.removeEventListener("abort", abortHandler);
      }

      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          const payload = JSON.parse(xhr.responseText);
          resolve(payload as UploadResponse);
        } catch (error) {
          reject(error instanceof Error ? error : new Error("Invalid JSON response"));
        }
      } else {
        reject(new Error(xhr.responseText || `Upload failed with status ${xhr.status}`));
      }
    };

    xhr.send(formData);
  });
}
