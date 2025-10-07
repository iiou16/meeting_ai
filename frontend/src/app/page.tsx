import Dashboard from "../components/dashboard";
import type { Language } from "../lib/i18n";

type PageProps = {
  searchParams?: { lang?: string };
};

export default function Home({ searchParams }: PageProps) {
  const initialLanguage: Language =
    searchParams?.lang === "en" ? "en" : "ja";
  return <Dashboard initialLanguage={initialLanguage} />;
}
