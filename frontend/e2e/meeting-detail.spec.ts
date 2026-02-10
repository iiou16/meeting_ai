import { test, expect } from "@playwright/test";
import { mockApi } from "./helpers/mock-api";

test.describe("ミーティング詳細画面", () => {
  test("要約・アクションアイテム・文字起こしが表示される", async ({
    page,
  }) => {
    await mockApi(page);
    await page.goto("/meetings/job-e2e-001?lang=ja");

    await expect(page.getByRole("heading", { level: 1 })).toContainText(
      "ジョブ詳細",
    );
    await expect(page.getByRole("heading", { level: 1 })).toContainText(
      "job-e2e-001",
    );

    // 要約セクション
    await expect(page.getByText("タイムスタンプ付きサマリー")).toBeVisible();
    await expect(
      page.getByText("会議のゴールを確認しました。"),
    ).toBeVisible();
    await expect(page.getByText("導入")).toBeVisible();

    // アクションアイテムセクション
    await expect(
      page.getByRole("heading", { name: "アクションアイテム" }),
    ).toBeVisible();
    await expect(page.getByText("資料を共有する。")).toBeVisible();
    await expect(page.getByText("田中")).toBeVisible();

    // 文字起こしセクション
    await expect(page.getByText("文字起こし全文")).toBeVisible();
    await expect(
      page.getByText("本日のアジェンダを確認します。"),
    ).toBeVisible();
    await expect(
      page.getByText("次のステップを議論しましょう。"),
    ).toBeVisible();
  });

  test("文字起こし検索でセグメントが絞り込まれる", async ({ page }) => {
    await mockApi(page);
    await page.goto("/meetings/job-e2e-001?lang=ja");

    await expect(
      page.getByText("本日のアジェンダを確認します。"),
    ).toBeVisible();
    await expect(
      page.getByText("次のステップを議論しましょう。"),
    ).toBeVisible();

    const searchInput = page.getByPlaceholder("キーワードで絞り込み");
    await searchInput.fill("アジェンダ");

    await expect(
      page.getByText("本日のアジェンダを確認します。"),
    ).toBeVisible();
    await expect(
      page.getByText("次のステップを議論しましょう。"),
    ).not.toBeVisible();
  });

  test("エクスポートボタンが存在する", async ({ page }) => {
    await mockApi(page);
    await page.goto("/meetings/job-e2e-001?lang=ja");

    await expect(
      page.getByText("会議のゴールを確認しました。"),
    ).toBeVisible();

    const exportButton = page.getByRole("button", {
      name: "JSONでダウンロード",
    });
    await expect(exportButton).toBeVisible();
    await expect(exportButton).toBeEnabled();
  });

  test("ダッシュボードへの戻りリンクが機能する", async ({ page }) => {
    await mockApi(page);
    await page.goto("/meetings/job-e2e-001?lang=ja");

    const backLink = page.getByRole("link", { name: "ジョブ一覧へ戻る" });
    await expect(backLink).toBeVisible();
    await expect(backLink).toHaveAttribute("href", "/?lang=ja");
  });

  test("日本語から英語に言語切り替えできる", async ({ page }) => {
    await mockApi(page);
    await page.goto("/meetings/job-e2e-001?lang=ja");

    await expect(page.getByText("タイムスタンプ付きサマリー")).toBeVisible();

    await page.getByRole("button", { name: "English" }).click();

    await expect(page.getByText("Timestamped Summaries")).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "Action Items" }),
    ).toBeVisible();
    await expect(page.getByText("Full Transcript")).toBeVisible();
  });

  test("API取得失敗時にエラーメッセージが表示される", async ({ page }) => {
    await mockApi(page, { meetingStatus: 500 });
    await page.goto("/meetings/job-e2e-001?lang=ja");

    await expect(page.getByText("データの取得に失敗しました")).toBeVisible();
  });

  test("失敗ジョブの詳細ページでも部分データが表示される", async ({
    page,
  }) => {
    const partialMeeting = {
      job_id: "job-e2e-failed",
      summary_items: [],
      action_items: [],
      segments: [
        {
          segment_id: "seg-partial",
          job_id: "job-e2e-failed",
          order: 0,
          start_ms: 0,
          end_ms: 30_000,
          text: "部分的に残ったデータ。",
          language: "ja",
          speaker_label: "司会",
        },
      ],
      quality_metrics: null,
    };
    await mockApi(page, { meeting: partialMeeting });
    await page.goto("/meetings/job-e2e-failed?lang=ja");

    await expect(page.getByText("job-e2e-failed")).toBeVisible();
    await expect(page.getByText("サマリーがまだありません。")).toBeVisible();
    await expect(
      page.getByText("アクションアイテムは検出されませんでした。"),
    ).toBeVisible();
    await expect(page.getByText("部分的に残ったデータ。")).toBeVisible();
  });
});
