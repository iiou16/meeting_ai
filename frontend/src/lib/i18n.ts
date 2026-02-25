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
    title: string;
    status: string;
    progress: string;
    recordedAt: string;
    updatedAt: string;
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
  meetingExportMarkdownButton: string;
  failedAtStage: (stage: string) => string;
  failureOccurredAt: (time: string) => string;
  titlePlaceholder: string;
  titleEditLabel: string;
  titleSaveSuccess: string;
  titleSaveError: string;
  recordedAtEditLabel: string;
  recordedAtPlaceholder: string;
  recordedAtSaveSuccess: string;
  recordedAtSaveError: string;
  speakerHeading: string;
  speakerLabelColumn: string;
  speakerNameColumn: string;
  speakerOrgColumn: string;
  speakerActionsColumn: string;
  speakerNamePlaceholder: string;
  speakerOrgPlaceholder: string;
  speakerSave: string;
  speakerReset: string;
  speakerSaveSuccess: string;
  speakerSaveError: string;
  speakerSelectMergeSource: string;
  speakerMergeInto: string;
  speakerUnmerge: string;
  speakerMergedFrom: (labels: string) => string;
  transcriptionLanguageLabel: string;
  transcriptionLanguageNames: Record<"ja" | "en", string>;
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
      title: "タイトル",
      status: "ステータス",
      progress: "進捗",
      recordedAt: "収録日時",
      updatedAt: "最終更新",
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
    meetingExportMarkdownButton: "Markdownでダウンロード",
    failedAtStage: (stage: string) =>
      `${stage} で失敗しました`,
    failureOccurredAt: (time: string) => `発生日時: ${time}`,
    titlePlaceholder: "タイトルを入力...",
    titleEditLabel: "タイトルを編集",
    titleSaveSuccess: "タイトルを保存しました。",
    titleSaveError: "タイトルの保存に失敗しました: ",
    recordedAtEditLabel: "収録日時を編集",
    recordedAtPlaceholder: "収録日時を設定...",
    recordedAtSaveSuccess: "収録日時を保存しました。",
    recordedAtSaveError: "収録日時の保存に失敗しました: ",
    speakerHeading: "話者プロフィール",
    speakerLabelColumn: "ラベル",
    speakerNameColumn: "名前",
    speakerOrgColumn: "所属",
    speakerActionsColumn: "操作",
    speakerNamePlaceholder: "名前を入力...",
    speakerOrgPlaceholder: "所属を入力...",
    speakerSave: "保存",
    speakerReset: "リセット",
    speakerSaveSuccess: "話者プロフィールを保存しました。",
    speakerSaveError: "話者プロフィールの保存に失敗しました: ",
    speakerSelectMergeSource: "統合元に選択",
    speakerMergeInto: "ここに統合",
    speakerUnmerge: "統合解除",
    speakerMergedFrom: (labels: string) => `統合元: ${labels}`,
    transcriptionLanguageLabel: "文字起こし言語",
    transcriptionLanguageNames: {
      ja: "日本語",
      en: "English",
    },
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
      title: "Title",
      status: "Status",
      progress: "Progress",
      recordedAt: "Recorded At",
      updatedAt: "Last Update",
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
    meetingExportMarkdownButton: "Download as Markdown",
    failedAtStage: (stage: string) =>
      `Failed at ${stage}`,
    failureOccurredAt: (time: string) => `Occurred at: ${time}`,
    titlePlaceholder: "Enter title...",
    titleEditLabel: "Edit title",
    titleSaveSuccess: "Title saved successfully.",
    titleSaveError: "Failed to save title: ",
    recordedAtEditLabel: "Edit recorded date",
    recordedAtPlaceholder: "Set recorded date...",
    recordedAtSaveSuccess: "Recorded date saved successfully.",
    recordedAtSaveError: "Failed to save recorded date: ",
    speakerHeading: "Speaker Profiles",
    speakerLabelColumn: "Label",
    speakerNameColumn: "Name",
    speakerOrgColumn: "Organization",
    speakerActionsColumn: "Actions",
    speakerNamePlaceholder: "Enter name...",
    speakerOrgPlaceholder: "Enter organization...",
    speakerSave: "Save",
    speakerReset: "Reset",
    speakerSaveSuccess: "Speaker profiles saved successfully.",
    speakerSaveError: "Failed to save speaker profiles: ",
    speakerSelectMergeSource: "Select as merge source",
    speakerMergeInto: "Merge into this",
    speakerUnmerge: "Unmerge",
    speakerMergedFrom: (labels: string) => `Merged from: ${labels}`,
    transcriptionLanguageLabel: "Transcription language",
    transcriptionLanguageNames: {
      ja: "Japanese",
      en: "English",
    },
  };
}

export const translations: Record<Language, BaseCopy> = {
  ja: jaCopy(),
  en: enCopy(),
};

export function getCopy(language: Language): BaseCopy {
  return translations[language];
}
