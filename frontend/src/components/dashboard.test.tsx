import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import Dashboard from "./dashboard";

const JOBS_FIXTURE = [
  {
    job_id: "job-123",
    status: "completed",
    created_at: "2025-05-25T10:00:00Z",
    updated_at: "2025-05-25T11:00:00Z",
    progress: 1,
    stage_index: 4,
    stage_count: 4,
    stage_key: "summary",
    duration_ms: 120_000,
    languages: ["ja"],
    summary_count: 3,
    action_item_count: 2,
    can_delete: true,
  },
];

const originalFetch = global.fetch;
let confirmSpy: jest.SpyInstance;

describe("Dashboard component", () => {
  beforeEach(() => {
    const jobsResponses = [JOBS_FIXTURE, []];
    global.fetch = jest
      .fn()
      .mockImplementation((input: RequestInfo, init?: RequestInit) => {
        const url = typeof input === "string" ? input : input.toString();
        const method = init?.method ?? "GET";

        if (url.includes("/api/jobs") && method === "GET") {
          const payload = jobsResponses.shift() ?? [];
          return Promise.resolve({
            ok: true,
            status: 200,
            json: () => Promise.resolve(payload),
          } as Response);
        }

        if (url.includes("/api/meetings") && method === "DELETE") {
          return Promise.resolve({
            ok: true,
            status: 204,
            json: async () => null,
          } as Response);
        }

        return Promise.reject(new Error(`Unexpected fetch call ${method} ${url}`));
      }) as unknown as typeof fetch;

    confirmSpy = jest.spyOn(window, "confirm").mockReturnValue(true);
  });

  afterEach(() => {
    (global.fetch as jest.Mock).mockReset();
    global.fetch = originalFetch;
    confirmSpy.mockRestore();
  });

  it("renders job list and updates language", async () => {
    render(<Dashboard initialLanguage="ja" />);

    await waitFor(() =>
      expect(screen.getByText("job-123")).toBeInTheDocument(),
    );

    expect(
      screen.getByRole("columnheader", { name: "ジョブID" }),
    ).toBeInTheDocument();
    expect(screen.getByText("完了")).toBeInTheDocument();
    expect(screen.getByText("4/4 · 要約生成")).toBeInTheDocument();
    expect(screen.getByText("ジョブを削除")).toBeInTheDocument();

    const englishButton = screen.getByRole("button", { name: "English" });
    await userEvent.click(englishButton);

    expect(
      screen.getByRole("columnheader", { name: "Job ID" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Completed")).toBeInTheDocument();
    expect(screen.getByText("4/4 · Summary")).toBeInTheDocument();
    const deleteButton = screen.getByRole("button", { name: "Delete job" });
    await userEvent.click(deleteButton);

    await waitFor(() =>
      expect(screen.queryByText("job-123")).not.toBeInTheDocument(),
    );
    expect(screen.getByText("Job deleted successfully.")).toBeInTheDocument();
    expect((global.fetch as jest.Mock).mock.calls.some((call) => {
      const [url, init] = call;
      return (
        typeof url === "string" &&
        url.includes("/api/meetings/job-123") &&
        (init?.method ?? "GET") === "DELETE"
      );
    })).toBe(true);
  });
});
