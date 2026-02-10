import type { Page } from "@playwright/test";
import type { JobSummary, MeetingDetail } from "../../src/lib/api";
import { JOBS_FIXTURE, MEETING_FIXTURE } from "../fixtures/api-data";

const API_BASE = "http://localhost:8000";

type MockApiOptions = {
  jobs?: JobSummary[];
  meeting?: MeetingDetail;
  jobsStatus?: number;
  meetingStatus?: number;
};

export async function mockApi(
  page: Page,
  options: MockApiOptions = {},
): Promise<void> {
  const {
    jobs = JOBS_FIXTURE,
    meeting = MEETING_FIXTURE,
    jobsStatus = 200,
    meetingStatus = 200,
  } = options;

  await page.route(`${API_BASE}/api/jobs`, (route) => {
    if (route.request().method() === "GET") {
      if (jobsStatus !== 200) {
        return route.fulfill({
          status: jobsStatus,
          contentType: "application/json",
          body: JSON.stringify({ detail: "Internal server error" }),
        });
      }
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(jobs),
      });
    }
    return route.continue();
  });

  await page.route(`${API_BASE}/api/jobs/*`, (route) => {
    if (route.request().method() === "GET") {
      const url = route.request().url();
      const jobId = url.split("/api/jobs/")[1];
      const job = jobs.find((j) => j.job_id === jobId);
      if (job) {
        return route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(job),
        });
      }
      return route.fulfill({ status: 404, body: "job not found" });
    }
    return route.continue();
  });

  await page.route(`${API_BASE}/api/meetings/*`, (route) => {
    const method = route.request().method();
    if (method === "GET") {
      if (meetingStatus !== 200) {
        return route.fulfill({
          status: meetingStatus,
          contentType: "application/json",
          body: JSON.stringify({ detail: "Internal server error" }),
        });
      }
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(meeting),
      });
    }
    if (method === "DELETE") {
      return route.fulfill({ status: 204, body: "" });
    }
    return route.continue();
  });

  await page.route(`${API_BASE}/api/videos`, (route) => {
    if (route.request().method() === "POST") {
      return route.fulfill({
        status: 202,
        contentType: "application/json",
        body: JSON.stringify({ job_id: "job-uploaded" }),
      });
    }
    return route.continue();
  });
}
