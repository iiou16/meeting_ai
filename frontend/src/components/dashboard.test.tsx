import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import Dashboard from "./dashboard";

const JOBS_FIXTURE = [
  {
    job_id: "job-123",
    title: null,
    status: "completed",
    created_at: "2025-05-25T10:00:00Z",
    updated_at: "2025-05-25T11:00:00Z",
    recorded_at: "2025-05-25T09:00:00+09:00",
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
      expect(screen.getByText("job-1\u2026")).toBeInTheDocument(),
    );

    expect(
      screen.getByRole("columnheader", { name: "ジョブID" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("columnheader", { name: "収録日時" }),
    ).toBeInTheDocument();
    expect(screen.getByText("完了")).toBeInTheDocument();
    expect(screen.getByText("4/4 · 要約生成")).toBeInTheDocument();
    expect(screen.getByText("100%")).toBeInTheDocument();
    expect(screen.getByText("ジョブを削除")).toBeInTheDocument();

    const progressBar = screen.getByRole("progressbar");
    expect(progressBar).toBeInTheDocument();
    expect(progressBar).toHaveAttribute("aria-valuenow", "100");
    expect(progressBar).toHaveAttribute("aria-valuemin", "0");
    expect(progressBar).toHaveAttribute("aria-valuemax", "100");

    const englishButton = screen.getByRole("button", { name: "English" });
    await userEvent.click(englishButton);

    expect(
      screen.getByRole("columnheader", { name: "Job ID" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("columnheader", { name: "Recorded At" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Completed")).toBeInTheDocument();
    expect(screen.getByText("4/4 · Summary")).toBeInTheDocument();
    const deleteButton = screen.getByRole("button", { name: "Delete job" });
    await userEvent.click(deleteButton);

    await waitFor(() =>
      expect(screen.queryByText("job-1\u2026")).not.toBeInTheDocument(),
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

  it("renders title column header and placeholder for null title", async () => {
    render(<Dashboard initialLanguage="ja" />);

    await waitFor(() =>
      expect(screen.getByText("job-1\u2026")).toBeInTheDocument(),
    );

    expect(
      screen.getByRole("columnheader", { name: "タイトル" }),
    ).toBeInTheDocument();

    const titleDisplay = screen.getByTestId("title-display");
    expect(titleDisplay).toBeInTheDocument();
    expect(titleDisplay).toHaveTextContent("タイトルを入力...");
  });

  it("allows inline title editing with Enter key", async () => {
    const user = userEvent.setup();

    const jobsWithTitle = [
      {
        ...JOBS_FIXTURE[0],
        title: "更新済みタイトル",
      },
    ];

    (global.fetch as jest.Mock).mockImplementation(
      (input: RequestInfo, init?: RequestInit) => {
        const url = typeof input === "string" ? input : input.toString();
        const method = init?.method ?? "GET";

        if (url.includes("/api/jobs") && method === "GET") {
          return Promise.resolve({
            ok: true,
            status: 200,
            json: () => Promise.resolve(jobsWithTitle),
          } as Response);
        }

        if (url.includes("/api/jobs/") && method === "PATCH") {
          return Promise.resolve({
            ok: true,
            json: () =>
              Promise.resolve({
                ...jobsWithTitle[0],
                title: "新しいタイトル",
              }),
          } as Response);
        }

        return Promise.reject(
          new Error(`Unexpected fetch call ${method} ${url}`),
        );
      },
    );

    render(<Dashboard initialLanguage="ja" />);

    await waitFor(() =>
      expect(screen.getByText("更新済みタイトル")).toBeInTheDocument(),
    );

    const titleDisplay = screen.getByTestId("title-display");
    await user.click(titleDisplay);

    const input = screen.getByTestId("title-input");
    expect(input).toBeInTheDocument();

    await user.clear(input);
    await user.type(input, "新しいタイトル{Enter}");

    await waitFor(() => {
      expect(
        (global.fetch as jest.Mock).mock.calls.some((call) => {
          const [callUrl, callInit] = call;
          return (
            typeof callUrl === "string" &&
            callUrl.includes("/api/jobs/") &&
            (callInit?.method ?? "GET") === "PATCH"
          );
        }),
      ).toBe(true);
    });
  });

  it("renders progress bar with partial progress", async () => {
    const partialJobs = [
      {
        job_id: "job-partial",
        status: "processing",
        created_at: "2025-05-25T10:00:00Z",
        updated_at: "2025-05-25T10:05:00Z",
        progress: 0.467,
        stage_index: 2,
        stage_count: 4,
        stage_key: "transcription",
        duration_ms: null,
        languages: [],
        summary_count: 0,
        action_item_count: 0,
        can_delete: false,
        sub_progress_completed: 5,
        sub_progress_total: 9,
      },
    ];

    (global.fetch as jest.Mock).mockImplementation(
      (input: RequestInfo, init?: RequestInit) => {
        const url = typeof input === "string" ? input : input.toString();
        const method = init?.method ?? "GET";
        if (url.includes("/api/jobs") && method === "GET") {
          return Promise.resolve({
            ok: true,
            status: 200,
            json: () => Promise.resolve(partialJobs),
          } as Response);
        }
        return Promise.reject(
          new Error(`Unexpected fetch call ${method} ${url}`),
        );
      },
    );

    render(<Dashboard initialLanguage="ja" />);

    await waitFor(() =>
      expect(screen.getByText("job-p\u2026")).toBeInTheDocument(),
    );

    const progressBar = screen.getByRole("progressbar");
    expect(progressBar).toHaveAttribute("aria-valuenow", "47");
    expect(screen.getByText("47%")).toBeInTheDocument();
    expect(
      screen.getByText("2/4 · 文字起こし生成（5/9）"),
    ).toBeInTheDocument();
  });
});
