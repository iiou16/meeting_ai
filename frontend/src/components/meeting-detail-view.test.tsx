import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { fetchMeeting } from "../lib/api";
import { MeetingDetailView } from "./meeting-detail-view";

jest.mock("../lib/api", () => {
  const actual = jest.requireActual("../lib/api");
  return {
    ...actual,
    fetchMeeting: jest.fn(),
  };
});

const mockedFetchMeeting = fetchMeeting as jest.MockedFunction<
  typeof fetchMeeting
>;

const MEETING_FIXTURE = {
  job_id: "job-777",
  summary_items: [
    {
      summary_id: "sum-1",
      job_id: "job-777",
      order: 0,
      segment_start_ms: 0,
      segment_end_ms: 60000,
      summary_text: "会議のゴールを確認しました。",
      heading: "導入",
      priority: "高",
      highlights: ["ゴール共有"],
    },
  ],
  action_items: [
    {
      action_id: "act-1",
      job_id: "job-777",
      order: 0,
      description: "資料を共有する。",
      owner: "田中",
      due_date: "2025-05-30",
      segment_start_ms: 0,
      segment_end_ms: 60000,
      priority: null,
    },
  ],
  segments: [
    {
      segment_id: "seg-1",
      job_id: "job-777",
      order: 0,
      start_ms: 0,
      end_ms: 60000,
      text: "本日のアジェンダを確認します。",
      language: "ja",
      speaker_label: "司会",
    },
  ],
  quality_metrics: {
    coverage_ratio: 0.9,
  },
};

describe("MeetingDetailView", () => {
  beforeEach(() => {
    mockedFetchMeeting.mockResolvedValue(MEETING_FIXTURE);
  });

  afterEach(() => {
    mockedFetchMeeting.mockReset();
  });

  it("renders meeting data and toggles language", async () => {
    render(
      <MeetingDetailView jobId="job-777" initialLanguage="ja" />,
    );

    await waitFor(() =>
      expect(screen.getByText(/会議のゴールを確認しました。/)).toBeInTheDocument(),
    );

    expect(
      screen.getByRole("button", { name: /JSONでダウンロード/ }),
    ).toBeInTheDocument();

    expect(mockedFetchMeeting).toHaveBeenCalledWith("job-777");
    expect(
      screen.getByRole("button", { name: "日本語" }),
    ).toHaveAttribute("aria-pressed", "true");

    const englishButton = screen.getByRole("button", { name: "English" });
    await userEvent.click(englishButton);

    expect(
      screen.getByText(/Meeting detail · job-777/i),
    ).toBeInTheDocument();
    expect(englishButton).toHaveAttribute("aria-pressed", "true");
  });
});
