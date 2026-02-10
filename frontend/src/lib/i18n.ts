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
  stageLabels: Record<string, string>;
  deleteButton: string;
  deleteInProgress: string;
  deleteSuccess: string;
  deleteError: string;
  deleteConfirm: (jobId: string) => string;
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
  stageLabels: Record<string, string>;
  deleteButton: string;
  deleteInProgress: string;
  deleteConfirm: (jobId: string) => string;
  deleteSuccess: string;
  deleteError: string;
};

function jaCopy(): BaseCopy {
  return {
    heroTitle: "MeetingAI ダッシュボード",
    heroSubtitle:
      "会議録画をアップロードすると、文字起こし・要約・アクションアイテムを自動生成します。",
    uploadSectionTitle: "録画ファイルをアップロード",
    uploadHelpText:
      "MP4 / MOV / WebM / MP3 / WAV / M4A ファイルに対応しています。アップロード後、自動的に処理が開始されます。",
    uploadButton: "アップロード開始",
    uploadSelectLabel: "動画・音声ファイル",
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
    stageLabels: {
      upload: "アップロード完了",
      chunking: "音声チャンク生成",
      transcription: "文字起こし生成",
      summary: "要約生成",
    },
    deleteButton: "ジョブを削除",
    deleteInProgress: "削除中...",
    deleteSuccess: "ジョブを削除しました。",
    deleteError: "ジョブの削除に失敗しました: ",
    deleteConfirm: (jobId: string) => `ジョブ ${jobId} を削除しますか？`,
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
    stageLabels: {
      ingest: "音声抽出",
      transcribe: "文字起こし",
      summarize: "要約生成",
      summary: "要約生成",
    },
    deleteButton: "削除",
    deleteInProgress: "削除中…",
    deleteConfirm: (jobId: string) =>
      `ジョブ ${jobId} を削除してよろしいですか？`,
    deleteSuccess: "ジョブを削除しました。",
    deleteError: "ジョブの削除に失敗しました: ",
  };
}

function enCopy(): BaseCopy {
  return {
    heroTitle: "MeetingAI Dashboard",
    heroSubtitle:
      "Upload meeting recordings to receive transcripts, summaries, and action items automatically.",
    uploadSectionTitle: "Upload Recording",
    uploadHelpText:
      "Supports MP4 / MOV / WebM / MP3 / WAV / M4A files. Processing starts automatically once the upload finishes.",
    uploadButton: "Start Upload",
    uploadSelectLabel: "Video / Audio file",
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
    stageLabels: {
      upload: "Upload complete",
      chunking: "Audio chunking",
      transcription: "Transcription",
      summary: "Summary",
    },
    deleteButton: "Delete job",
    deleteInProgress: "Deleting…",
    deleteSuccess: "Job deleted successfully.",
    deleteError: "Failed to delete job: ",
    deleteConfirm: (jobId: string) => `Delete job ${jobId}?`,
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
    stageLabels: {
      ingest: "Audio extraction",
      transcribe: "Transcription",
      summarize: "Summarisation",
      summary: "Summarisation",
    },
    deleteButton: "Delete",
    deleteInProgress: "Deleting…",
    deleteConfirm: (jobId: string) =>
      `Are you sure you want to delete job ${jobId}?`,
    deleteSuccess: "Job deleted successfully.",
    deleteError: "Failed to delete job: ",
  };
}

export const translations: Record<Language, BaseCopy> = {
  ja: jaCopy(),
  en: enCopy(),
};

export function getCopy(language: Language): BaseCopy {
  return translations[language];
}
