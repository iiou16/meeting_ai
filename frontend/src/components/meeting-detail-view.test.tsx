import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import {
  fetchMeeting,
  fetchMeetingMarkdown,
  fetchJob,
  updateJobTitle,
} from "../lib/api";
import { MeetingDetailView } from "./meeting-detail-view";

global.URL.createObjectURL = jest.fn(() => "blob:mock-url");
global.URL.revokeObjectURL = jest.fn();

jest.mock("../lib/api", () => {
  const actual = jest.requireActual("../lib/api");
  return {
    ...actual,
    fetchMeeting: jest.fn(),
    fetchMeetingMarkdown: jest.fn(),
    fetchJob: jest.fn(),
    updateJobTitle: jest.fn(),
  };
});

const mockedFetchMeeting = fetchMeeting as jest.MockedFunction<
  typeof fetchMeeting
>;
const mockedFetchMeetingMarkdown = fetchMeetingMarkdown as jest.MockedFunction<
  typeof fetchMeetingMarkdown
>;
const mockedFetchJob = fetchJob as jest.MockedFunction<typeof fetchJob>;
const mockedUpdateJobTitle = updateJobTitle as jest.MockedFunction<
  typeof updateJobTitle
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

const JOB_DETAIL_FIXTURE = {
  job_id: "job-777",
  title: "テスト会議タイトル",
  status: "completed" as const,
  created_at: "2025-05-25T10:00:00Z",
  updated_at: "2025-05-25T11:00:00Z",
  progress: 1,
  stage_index: 4,
  stage_count: 4,
  stage_key: "summary",
  can_delete: true,
  languages: ["ja"],
  summary_count: 1,
  action_item_count: 1,
};

describe("MeetingDetailView", () => {
  beforeEach(() => {
    mockedFetchMeeting.mockResolvedValue(MEETING_FIXTURE);
    mockedFetchMeetingMarkdown.mockResolvedValue(new Blob(["# Test"], { type: "text/markdown" }));
    mockedFetchJob.mockResolvedValue(JOB_DETAIL_FIXTURE);
  });

  afterEach(() => {
    mockedFetchMeeting.mockReset();
    mockedFetchMeetingMarkdown.mockReset();
    mockedFetchJob.mockReset();
    mockedUpdateJobTitle.mockReset();
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

  it("renders transcript with inline timestamps and speaker label", async () => {
    render(<MeetingDetailView jobId="job-777" initialLanguage="ja" />);
    await waitFor(() =>
      expect(screen.getByText(/本日のアジェンダを確認します。/)).toBeInTheDocument(),
    );
    // インラインタイムスタンプ
    expect(screen.getByText("[00:00]")).toBeInTheDocument();
    // スピーカーラベル
    expect(screen.getByText(/司会:/)).toBeInTheDocument();
  });

  it("displays job title in header", async () => {
    render(<MeetingDetailView jobId="job-777" initialLanguage="ja" />);

    await waitFor(() =>
      expect(screen.getByTestId("detail-title-display")).toBeInTheDocument(),
    );

    expect(screen.getByTestId("detail-title-display")).toHaveTextContent(
      "テスト会議タイトル",
    );
  });

  it("displays placeholder when title is null", async () => {
    mockedFetchJob.mockResolvedValue({
      ...JOB_DETAIL_FIXTURE,
      title: null,
    });

    render(<MeetingDetailView jobId="job-777" initialLanguage="ja" />);

    await waitFor(() =>
      expect(screen.getByTestId("detail-title-display")).toBeInTheDocument(),
    );

    expect(screen.getByTestId("detail-title-display")).toHaveTextContent(
      "タイトルを入力...",
    );
  });

  it("renders markdown export button", async () => {
    render(
      <MeetingDetailView jobId="job-777" initialLanguage="ja" />,
    );

    await waitFor(() =>
      expect(screen.getByText(/会議のゴールを確認しました。/)).toBeInTheDocument(),
    );

    expect(
      screen.getByRole("button", { name: /Markdownでダウンロード/ }),
    ).toBeInTheDocument();
  });

  it("calls fetchMeetingMarkdown when markdown button is clicked", async () => {
    const user = userEvent.setup();

    render(
      <MeetingDetailView jobId="job-777" initialLanguage="ja" />,
    );

    await waitFor(() =>
      expect(screen.getByText(/会議のゴールを確認しました。/)).toBeInTheDocument(),
    );

    const mdButton = screen.getByRole("button", { name: /Markdownでダウンロード/ });
    await user.click(mdButton);

    expect(mockedFetchMeetingMarkdown).toHaveBeenCalledWith("job-777");
  });

  it("allows inline title editing via click and Enter", async () => {
    const user = userEvent.setup();
    mockedUpdateJobTitle.mockResolvedValue({
      ...JOB_DETAIL_FIXTURE,
      title: "新しいタイトル",
    });

    render(<MeetingDetailView jobId="job-777" initialLanguage="ja" />);

    await waitFor(() =>
      expect(screen.getByTestId("detail-title-display")).toBeInTheDocument(),
    );

    await user.click(screen.getByTestId("detail-title-display"));

    const input = screen.getByTestId("detail-title-input");
    expect(input).toBeInTheDocument();

    await user.clear(input);
    await user.type(input, "新しいタイトル{Enter}");

    await waitFor(() =>
      expect(mockedUpdateJobTitle).toHaveBeenCalledWith(
        "job-777",
        "新しいタイトル",
      ),
    );
  });
});
