import { MeetingDetailView } from "../../../components/meeting-detail-view";
import type { Language } from "../../../lib/i18n";

type PageProps = {
  params: Promise<{ jobId: string }>;
  searchParams?: { lang?: string };
};

export default async function MeetingPage({ params, searchParams }: PageProps) {
  const resolvedParams = await params;
  const initialLanguage: Language =
    searchParams?.lang === "en" ? "en" : "ja";

  return (
    <MeetingDetailView
      jobId={resolvedParams.jobId}
      initialLanguage={initialLanguage}
    />
  );
}
