import { MeetingDetailView } from "../../../components/meeting-detail-view";
import type { Language } from "../../../lib/i18n";

type PageProps = {
  params: Promise<{ jobId: string }>;
  searchParams?: Promise<{ lang?: string }>;
};

export default async function MeetingPage({ params, searchParams }: PageProps) {
  const { jobId } = await params;
  const search = await (searchParams ?? Promise.resolve({} as { lang?: string }));
  const initialLanguage: Language =
    search.lang === "en" ? "en" : "ja";

  return (
    <MeetingDetailView
      jobId={jobId}
      initialLanguage={initialLanguage}
    />
  );
}
