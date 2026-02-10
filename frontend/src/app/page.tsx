import Dashboard from "../components/dashboard";
import type { Language } from "../lib/i18n";

type PageProps = {
  searchParams?: Promise<{ lang?: string }>;
};

export default async function Home({ searchParams }: PageProps) {
  const search = await (searchParams ?? Promise.resolve({} as { lang?: string }));
  const initialLanguage: Language =
    search.lang === "en" ? "en" : "ja";
  return <Dashboard initialLanguage={initialLanguage} />;
}
