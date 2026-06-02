import { getTranslations, setRequestLocale } from "next-intl/server";
import ChatIsland from "./ChatIsland";

export default async function Home({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);
  const tWelcome = await getTranslations({ locale, namespace: "Welcome" });

  const heroContent = (
    <>
      <h2 className="text-2xl font-serif text-gray-700 mb-2">
        {tWelcome("heading")}
      </h2>
      <p className="text-gray-500 max-w-md mb-8">{tWelcome("description")}</p>
    </>
  );

  return <ChatIsland heroContent={heroContent} />;
}
