"use client";

import { useState, useEffect, useCallback } from "react";
import { useTranslations } from "next-intl";
import { warmupBackend } from "@/lib/api";

interface Phrase {
  text: string;
  lang: string;
  dir: "ltr" | "rtl";
  top: string;
  left?: string;
  right?: string;
  maxWidth: string;
  fontSize: string;
  opacity: number;
  floatDuration: number; // seconds
  floatDelay: number; // seconds
  staggerDelay: number; // ms
}

const PHRASES: Phrase[] = [
  {
    text: "You are never alone — God walks with you.",
    lang: "en",
    dir: "ltr",
    top: "7%",
    left: "4%",
    maxWidth: "240px",
    fontSize: "1.0rem",
    opacity: 0.75,
    floatDuration: 4.0,
    floatDelay: 0.0,
    staggerDelay: 0,
  },
  {
    text: "Non sei mai solo — Dio cammina con te.",
    lang: "it",
    dir: "ltr",
    top: "12%",
    left: "28%",
    maxWidth: "min(200px,45vw)",
    fontSize: "0.95rem",
    opacity: 0.6,
    floatDuration: 3.5,
    floatDelay: 0.6,
    staggerDelay: 150,
  },
  {
    text: "En Dios encontrarás paz que sobrepasa todo entendimiento.",
    lang: "es",
    dir: "ltr",
    top: "8%",
    right: "4%",
    maxWidth: "230px",
    fontSize: "1.0rem",
    opacity: 0.7,
    floatDuration: 4.8,
    floatDelay: 1.1,
    staggerDelay: 300,
  },
  {
    text: "Gottes Frieden bewahrt euch in Christus Jesus.",
    lang: "de",
    dir: "ltr",
    top: "28%",
    left: "2%",
    maxWidth: "210px",
    fontSize: "0.95rem",
    opacity: 0.65,
    floatDuration: 3.2,
    floatDelay: 0.3,
    staggerDelay: 450,
  },
  {
    text: "Dieu guérit les cœurs brisés et panse leurs plaies.",
    lang: "fr",
    dir: "ltr",
    top: "30%",
    right: "3%",
    maxWidth: "220px",
    fontSize: "0.97rem",
    opacity: 0.72,
    floatDuration: 4.3,
    floatDelay: 0.9,
    staggerDelay: 600,
  },
  {
    text: "A graça de Deus renova a alma cansada.",
    lang: "pt",
    dir: "ltr",
    top: "68%",
    left: "3%",
    maxWidth: "200px",
    fontSize: "0.92rem",
    opacity: 0.6,
    floatDuration: 3.8,
    floatDelay: 0.5,
    staggerDelay: 750,
  },
  {
    text: "Бог — наша крепость и опора в трудные времена.",
    lang: "ru",
    dir: "ltr",
    top: "65%",
    right: "2%",
    maxWidth: "225px",
    fontSize: "0.95rem",
    opacity: 0.68,
    floatDuration: 4.5,
    floatDelay: 1.4,
    staggerDelay: 900,
  },
  {
    text: "上帝的爱永无止尽，祂与你同在。",
    lang: "zh",
    dir: "ltr",
    top: "82%",
    left: "5%",
    maxWidth: "160px",
    fontSize: "1.02rem",
    opacity: 0.8,
    floatDuration: 3.0,
    floatDelay: 0.2,
    staggerDelay: 1050,
  },
  {
    text: "परमेश्वर तेरे साथ है — मत डर, मैं तेरा परमेश्वर हूँ।",
    lang: "hi",
    dir: "ltr",
    top: "87%",
    left: "30%",
    maxWidth: "min(220px,45vw)",
    fontSize: "0.92rem",
    opacity: 0.58,
    floatDuration: 4.2,
    floatDelay: 0.8,
    staggerDelay: 1200,
  },
  {
    text: "하나님의 사랑은 영원하고, 그분은 항상 함께 하십니다.",
    lang: "ko",
    dir: "ltr",
    top: "80%",
    right: "4%",
    maxWidth: "200px",
    fontSize: "0.97rem",
    opacity: 0.72,
    floatDuration: 3.6,
    floatDelay: 1.2,
    staggerDelay: 1350,
  },
  {
    text: "الله نور دربي وملجأ روحي في كل الأوقات.",
    lang: "ar",
    dir: "rtl",
    top: "14%",
    right: "22%",
    maxWidth: "min(210px,45vw)",
    fontSize: "0.95rem",
    opacity: 0.62,
    floatDuration: 4.0,
    floatDelay: 0.4,
    staggerDelay: 1500,
  },
];

const SPLASH_DURATION_MS = 5500;
const SPLASH_EXIT_MS = 700;

interface SplashScreenProps {
  onComplete: () => void;
}

export function SplashScreen({ onComplete }: SplashScreenProps) {
  const t = useTranslations("Splash");
  const [phrasesVisible, setPhrasesVisible] = useState(false);
  const [centerVisible, setCenterVisible] = useState(false);
  const [exiting, setExiting] = useState(false);

  const handleComplete = useCallback(onComplete, [onComplete]);

  useEffect(() => {
    warmupBackend(
      () => {},
      () => {},
    );

    const t1 = setTimeout(() => setPhrasesVisible(true), 50);
    const t2 = setTimeout(() => setCenterVisible(true), 800);
    const t3 = setTimeout(() => {
      setExiting(true);
      setTimeout(handleComplete, SPLASH_EXIT_MS);
    }, SPLASH_DURATION_MS);

    return () => [t1, t2, t3].forEach(clearTimeout);
  }, [handleComplete]);

  return (
    <div
      className="fixed inset-0 z-50"
      style={{
        background:
          "linear-gradient(160deg, #5b3427 0%, #874a30 50%, #b87444 100%)",
        opacity: exiting ? 0 : 1,
        transition: `opacity ${SPLASH_EXIT_MS}ms ease-out`,
        pointerEvents: exiting ? "none" : "auto",
      }}
      aria-hidden="true"
    >
      {/* Scattered phrases */}
      {PHRASES.map((phrase) => (
        <div
          key={phrase.lang}
          data-splash-phrase
          lang={phrase.lang}
          dir={phrase.dir}
          style={{
            position: "absolute",
            top: phrase.top,
            ...(phrase.left ? { left: phrase.left } : {}),
            ...(phrase.right ? { right: phrase.right } : {}),
            maxWidth: phrase.maxWidth,
            opacity: phrasesVisible ? phrase.opacity : 0,
            transition: `opacity 600ms ease-out ${phrase.staggerDelay}ms`,
            animation: `splash-float ${phrase.floatDuration}s ease-in-out ${phrase.floatDelay}s infinite`,
          }}
        >
          <p
            style={{
              color: "rgba(255,255,255,0.95)",
              fontSize: phrase.fontSize,
              fontStyle: "italic",
              lineHeight: 1.45,
              textAlign: phrase.dir === "rtl" ? "right" : "left",
              margin: 0,
            }}
          >
            {phrase.text}
          </p>
        </div>
      ))}

      {/* Center content */}
      <div
        className="absolute inset-0 flex flex-col items-center justify-center"
        style={{
          opacity: centerVisible ? 1 : 0,
          transform: centerVisible ? "translateY(0)" : "translateY(12px)",
          transition: "opacity 700ms ease-out, transform 700ms ease-out",
        }}
      >
        {/* Open book with soft light rays icon */}
        <div className="mb-6 opacity-90">
          <svg
            width="56"
            height="56"
            viewBox="0 0 56 56"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
            aria-hidden="true"
          >
            {/* Left page */}
            <path
              d="M26 32v8c0 1-0.5 1.5-1.5 1.8l-10 2.5c-1.2 0.3-2-0.3-2-1.5v-12c0-1.2 0.8-2 2-2.3l10-2.5c1-0.3 1.5 0.3 1.5 1.5z"
              fill="white"
            />
            {/* Right page */}
            <path
              d="M30 32v8c0 1 0.5 1.5 1.5 1.8l10 2.5c1.2 0.3 2-0.3 2-1.5v-12c0-1.2-0.8-2-2-2.3l-10-2.5c-1-0.3-1.5 0.3-1.5 1.5z"
              fill="white"
            />
            {/* Spine */}
            <rect x="27" y="27" width="2" height="17" rx="0.5" fill="white" />
            {/* Light ray center */}
            <path d="M27.5 26L28.5 26L28.2 14L27.8 14Z" fill="white" opacity="0.9" />
            {/* Light ray left */}
            <path d="M26.5 27L25.5 26.5L20 15L21.5 14.5Z" fill="white" opacity="0.6" />
            {/* Light ray right */}
            <path d="M29.5 27L30.5 26.5L36 15L34.5 14.5Z" fill="white" opacity="0.6" />
          </svg>
        </div>

        <h1 className="text-white text-2xl font-semibold mb-2 tracking-wide">
          {t("title")}
        </h1>
        <p className="text-white/60 text-sm tracking-wider uppercase">
          {t("motto")}
        </p>
      </div>
    </div>
  );
}
