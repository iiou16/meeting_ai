import { MeetingDetailView } from "../../../components/meeting-detail-view";
import type { Language } from "../../../lib/i18n";

type PageProps = {
  params: { jobId: string };
  searchParams?: { lang?: string };
};

export default function MeetingPage({ params, searchParams }: PageProps) {
  const initialLanguage: Language =
    searchParams?.lang === "en" ? "en" : "ja";

  return (
    <MeetingDetailView
      jobId={params.jobId}
      initialLanguage={initialLanguage}
    />
  );
}
