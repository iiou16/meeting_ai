import { test, expect } from "@playwright/test";
import { mockApi } from "./helpers/mock-api";
import {
  EMPTY_JOBS,
  FAILED_JOB,
  FAILED_JOB_NO_DETAILS,
  JOBS_WITH_FAILURE,
} from "./fixtures/api-data";

test.describe("ダッシュボード", () => {
  test("ページタイトルとヘッダーが表示される", async ({ page }) => {
    await mockApi(page);
    await page.goto("/");

    await expect(page.getByRole("heading", { level: 1 })).toContainText(
      "MeetingAI ダッシュボード",
    );
    await expect(
      page.getByText("会議録画をアップロードすると"),
    ).toBeVisible();
  });

  test("ジョブ一覧がテーブルに表示される", async ({ page }) => {
    await mockApi(page);
    await page.goto("/");

    await expect(page.getByText("処理ジョブ一覧")).toBeVisible();
    await expect(page.getByText("job-e2e-001")).toBeVisible();
    await expect(page.getByText("job-e2e-002")).toBeVisible();
    await expect(page.getByText("完了", { exact: true }).first()).toBeVisible();
    await expect(page.getByText("処理中", { exact: true }).first()).toBeVisible();
  });

  test("ジョブが空の場合に空メッセージが表示される", async ({ page }) => {
    await mockApi(page, { jobs: EMPTY_JOBS });
    await page.goto("/");

    await expect(
      page.getByText("まだジョブがありません"),
    ).toBeVisible();
  });

  test("ファイルアップロードフォームが存在する", async ({ page }) => {
    await mockApi(page);
    await page.goto("/");

    await expect(page.getByText("録画ファイルをアップロード")).toBeVisible();

    const fileInput = page.locator('input[type="file"]');
    await expect(fileInput).toBeAttached();

    const uploadButton = page.getByRole("button", { name: "アップロード開始" });
    await expect(uploadButton).toBeVisible();
    await expect(uploadButton).toBeDisabled();
  });

  test("詳細リンクが正しいhrefを持ち遷移先で内容が表示される", async ({
    page,
  }) => {
    await mockApi(page);
    await page.goto("/");

    await expect(page.getByText("job-e2e-001")).toBeVisible();

    const detailLink = page.getByRole("link", { name: "詳細を見る" }).first();
    await expect(detailLink).toBeVisible();
    await expect(detailLink).toHaveAttribute("href", /\/meetings\/job-e2e-001/);

    // Next.js client-side navigation を使わず、href先に直接遷移して確認
    const href = await detailLink.getAttribute("href");
    await page.goto(href!);

    await expect(page).toHaveURL(/\/meetings\/job-e2e-001/);
    await expect(page.getByRole("heading", { level: 1 })).toContainText(
      "job-e2e-001",
    );
    await expect(
      page.getByText("会議のゴールを確認しました。"),
    ).toBeVisible();
  });

  test("日本語から英語に言語切り替えできる", async ({ page }) => {
    await mockApi(page);
    await page.goto("/");

    await expect(page.getByRole("heading", { level: 1 })).toContainText(
      "MeetingAI ダッシュボード",
    );

    const enButton = page.getByRole("button", { name: "English" });
    await enButton.click();

    await expect(page.getByRole("heading", { level: 1 })).toContainText(
      "MeetingAI Dashboard",
    );
    await expect(page.getByText("Processing Jobs")).toBeVisible();
    await expect(enButton).toHaveAttribute("aria-pressed", "true");
  });

  test("API取得失敗時にエラーが表示される", async ({ page }) => {
    await mockApi(page, { jobsStatus: 500 });
    await page.goto("/");

    await expect(page.locator(".text-red-200")).toBeVisible();
  });
});

test.describe("失敗ジョブの表示", () => {
  test("失敗バッジとエラー詳細が表示される", async ({ page }) => {
    await mockApi(page, { jobs: JOBS_WITH_FAILURE });
    await page.goto("/");

    await expect(page.getByText("job-e2e-failed")).toBeVisible();

    await expect(
      page.getByText("失敗", { exact: true }).first(),
    ).toBeVisible();

    await expect(page.getByTestId("failure-stage").first()).toContainText(
      "音声チャンク生成",
    );

    await expect(page.getByTestId("failure-message").first()).toContainText(
      "Redis connection refused",
    );

    await expect(page.getByTestId("failure-time").first()).toBeVisible();
  });

  test("失敗ジョブは削除ボタンが表示されない", async ({ page }) => {
    await mockApi(page, { jobs: [FAILED_JOB] });
    await page.goto("/");

    await expect(page.getByText("job-e2e-failed")).toBeVisible();
    await expect(
      page.getByRole("button", { name: "ジョブを削除" }),
    ).not.toBeVisible();
  });

  test("英語で失敗ジョブの詳細が表示される", async ({ page }) => {
    await mockApi(page, { jobs: JOBS_WITH_FAILURE });
    await page.goto("/");

    await page.getByRole("button", { name: "English" }).click();

    await expect(
      page.getByText("Failed", { exact: true }).first(),
    ).toBeVisible();

    await expect(page.getByTestId("failure-stage").first()).toContainText(
      "Audio chunking",
    );
  });

  test("failure情報がないfailedジョブでも汎用メッセージが表示される", async ({
    page,
  }) => {
    await mockApi(page, { jobs: [FAILED_JOB_NO_DETAILS] });
    await page.goto("/");

    await expect(
      page.getByText("job-e2e-failed-no-detail"),
    ).toBeVisible();

    await expect(
      page.getByText("失敗", { exact: true }).first(),
    ).toBeVisible();

    await expect(
      page.getByText("エラーが発生しました。ログを確認してください。"),
    ).toBeVisible();
  });
});
