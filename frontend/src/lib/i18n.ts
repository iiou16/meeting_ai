export type Language = "ja" | "en";

type BaseCopy = {
  heroTitle: string;
  heroSubtitle: string;
  uploadSectionTitle: string;
  uploadHelpText: string;
  uploadButton: string;
  uploadSelectLabel: string;
  uploadSelectPlaceholder: string;
  uploadSuccess: string;
  uploadError: string;
  uploadSizeError: (limitMb: number) => string;
  uploadInProgress: (progress: number) => string;
  jobsSectionTitle: string;
  jobsEmpty: string;
  jobsHeaders: {
    jobId: string;
    status: string;
    progress: string;
    updatedAt: string;
    summary: string;
    actions: string;
  };
  statusLabels: Record<string, string>;
  statusDescriptions: Record<string, string>;
  viewDetails: string;
  refreshButton: string;
  lastUpdatedPrefix: string;
  languageNames: Record<Language, string>;
  meetingBackLink: string;
  meetingTitlePrefix: string;
  meetingSummaryHeading: string;
  meetingActionHeading: string;
  meetingTranscriptHeading: string;
  meetingSearchPlaceholder: string;
  meetingLoading: string;
  meetingError: string;
  meetingEmptySummary: string;
  meetingEmptyAction: string;
  meetingEmptyTranscript: string;
  meetingExportButton: string;
};

function jaCopy(): BaseCopy {
  return {
    heroTitle: "MeetingAI ダッシュボード",
    heroSubtitle:
      "会議録画をアップロードすると、文字起こし・要約・アクションアイテムを自動生成します。",
    uploadSectionTitle: "録画ファイルをアップロード",
    uploadHelpText:
      "MP4 / MOV / WebM ファイルに対応しています。アップロード後、自動的に処理が開始されます。",
    uploadButton: "アップロード開始",
    uploadSelectLabel: "動画ファイル",
    uploadSelectPlaceholder: "ファイルを選択してください",
    uploadSuccess: "アップロードが完了しました。処理状況はジョブ一覧で確認できます。",
    uploadError: "アップロードに失敗しました: ",
    uploadSizeError: (limitMb: number) =>
      `ファイルサイズが大きすぎます。${limitMb}MB 以下のファイルを指定してください。`,
    uploadInProgress: (progress: number) =>
      `アップロード中... ${progress}%`,
    jobsSectionTitle: "処理ジョブ一覧",
    jobsEmpty: "まだジョブがありません。ファイルをアップロードして開始しましょう。",
    jobsHeaders: {
      jobId: "ジョブID",
      status: "ステータス",
      progress: "進捗",
      updatedAt: "最終更新",
      summary: "サマリー数 / アクション数",
      actions: "操作",
    },
    statusLabels: {
      pending: "待機中",
      processing: "処理中",
      completed: "完了",
      failed: "失敗",
    },
    statusDescriptions: {
      pending: "キューに投入済み。ワーカーを待機しています。",
      processing: "音声抽出または文字起こし・要約を実行中です。",
      completed: "すべての処理が完了しました。",
      failed: "エラーが発生しました。ログを確認してください。",
    },
    viewDetails: "詳細を見る",
    refreshButton: "一覧を更新",
    lastUpdatedPrefix: "最終更新",
    languageNames: {
      ja: "日本語",
      en: "English",
    },
    meetingTitlePrefix: "ジョブ詳細",
    meetingBackLink: "ジョブ一覧へ戻る",
    meetingSummaryHeading: "タイムスタンプ付きサマリー",
    meetingActionHeading: "アクションアイテム",
    meetingTranscriptHeading: "文字起こし全文",
    meetingSearchPlaceholder: "キーワードで絞り込み",
    meetingLoading: "データを読み込み中です…",
    meetingError: "データの取得に失敗しました。",
    meetingEmptySummary: "サマリーがまだありません。",
    meetingEmptyAction: "アクションアイテムは検出されませんでした。",
    meetingEmptyTranscript: "文字起こしが見つかりませんでした。",
    meetingExportButton: "JSONでダウンロード",
  };
}

function enCopy(): BaseCopy {
  return {
    heroTitle: "MeetingAI Dashboard",
    heroSubtitle:
      "Upload meeting recordings to receive transcripts, summaries, and action items automatically.",
    uploadSectionTitle: "Upload Recording",
    uploadHelpText:
      "Supports MP4 / MOV / WebM files. Processing starts automatically once the upload finishes.",
    uploadButton: "Start Upload",
    uploadSelectLabel: "Video file",
    uploadSelectPlaceholder: "Choose a file",
    uploadSuccess:
      "Upload completed! Track the processing progress in the job list below.",
    uploadError: "Upload failed: ",
    uploadSizeError: (limitMb: number) =>
      `File is too large. Please select a file below ${limitMb}MB.`,
    uploadInProgress: (progress: number) =>
      `Uploading… ${progress}%`,
    jobsSectionTitle: "Processing Jobs",
    jobsEmpty: "No jobs yet. Upload a recording to get started.",
    jobsHeaders: {
      jobId: "Job ID",
      status: "Status",
      progress: "Progress",
      updatedAt: "Last Update",
      summary: "Summary / Actions",
      actions: "Actions",
    },
    statusLabels: {
      pending: "Pending",
      processing: "Processing",
      completed: "Completed",
      failed: "Failed",
    },
    statusDescriptions: {
      pending: "Queued and waiting for an available worker.",
      processing: "Audio extraction, transcription, or summarisation in progress.",
      completed: "Processing finished successfully.",
      failed: "Processing failed. Check worker logs.",
    },
    viewDetails: "View details",
    refreshButton: "Refresh list",
    lastUpdatedPrefix: "Last updated",
    languageNames: {
      ja: "Japanese",
      en: "English",
    },
    meetingTitlePrefix: "Meeting detail",
    meetingBackLink: "Back to dashboard",
    meetingSummaryHeading: "Timestamped Summaries",
    meetingActionHeading: "Action Items",
    meetingTranscriptHeading: "Full Transcript",
    meetingSearchPlaceholder: "Filter transcript…",
    meetingLoading: "Loading meeting data…",
    meetingError: "Failed to load meeting data.",
    meetingEmptySummary: "No summary results yet.",
    meetingEmptyAction: "No action items detected.",
    meetingEmptyTranscript: "No transcript segments found.",
    meetingExportButton: "Download as JSON",
  };
}

export const translations: Record<Language, BaseCopy> = {
  ja: jaCopy(),
  en: enCopy(),
};

export function getCopy(language: Language): BaseCopy {
  return translations[language];
}
