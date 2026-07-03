import { ImageResponse } from "next/og";
import { getTranslations } from "next-intl/server";

export const size = { width: 1200, height: 630 };
export const contentType = "image/png";
export const alt = "Vox Quieta";

export default async function Image({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "Metadata" });

  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          backgroundColor: "#3A2210",
        }}
      >
        <div
          style={{
            display: "flex",
            width: 160,
            height: 160,
            borderRadius: "50%",
            backgroundColor: "#F0B830",
            opacity: 0.25,
            position: "absolute",
            top: 90,
          }}
        />
        <div
          style={{
            display: "flex",
            width: 60,
            height: 60,
            borderRadius: "50%",
            backgroundColor: "#FFE880",
            position: "absolute",
            top: 140,
          }}
        />
        <div
          style={{
            display: "flex",
            marginTop: 140,
            fontSize: 72,
            fontWeight: 700,
            color: "#FFE880",
          }}
        >
          {t("title")}
        </div>
        <div
          style={{
            display: "flex",
            marginTop: 24,
            fontSize: 32,
            color: "#F5C842",
          }}
        >
          {t("description")}
        </div>
      </div>
    ),
    size,
  );
}
