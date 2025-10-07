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
    duration_ms: 120_000,
    languages: ["ja"],
    summary_count: 3,
    action_item_count: 2,
  },
];

function mockFetchSuccess() {
  const response = {
    ok: true,
    json: () => Promise.resolve(JOBS_FIXTURE),
  } as Response;
  return Promise.resolve(response);
}

const originalFetch = global.fetch;

describe("Dashboard component", () => {
  beforeEach(() => {
    global.fetch = jest
      .fn()
      .mockImplementation(mockFetchSuccess) as unknown as typeof fetch;
  });

  afterEach(() => {
    (global.fetch as jest.Mock).mockReset();
    global.fetch = originalFetch;
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

    const englishButton = screen.getByRole("button", { name: "English" });
    await userEvent.click(englishButton);

    expect(
      screen.getByRole("columnheader", { name: "Job ID" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Completed")).toBeInTheDocument();
  });
});
