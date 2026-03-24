"use client";

import { useState, useEffect, useCallback } from "react";
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
    text: "What does the Bible say about love?",
    lang: "en",
    dir: "ltr",
    top: "7%",
    left: "4%",
    maxWidth: "240px",
    fontSize: "0.85rem",
    opacity: 0.75,
    floatDuration: 4.0,
    floatDelay: 0.0,
    staggerDelay: 0,
  },
  {
    text: "Cosa dice la Bibbia sul perdono?",
    lang: "it",
    dir: "ltr",
    top: "12%",
    left: "28%",
    maxWidth: "min(200px,45vw)",
    fontSize: "0.80rem",
    opacity: 0.6,
    floatDuration: 3.5,
    floatDelay: 0.6,
    staggerDelay: 150,
  },
  {
    text: "¿Qué dice la Biblia sobre la esperanza?",
    lang: "es",
    dir: "ltr",
    top: "8%",
    right: "4%",
    maxWidth: "230px",
    fontSize: "0.85rem",
    opacity: 0.7,
    floatDuration: 4.8,
    floatDelay: 1.1,
    staggerDelay: 300,
  },
  {
    text: "Was sagt die Bibel über Frieden?",
    lang: "de",
    dir: "ltr",
    top: "28%",
    left: "2%",
    maxWidth: "210px",
    fontSize: "0.80rem",
    opacity: 0.65,
    floatDuration: 3.2,
    floatDelay: 0.3,
    staggerDelay: 450,
  },
  {
    text: "Que dit la Bible sur la foi?",
    lang: "fr",
    dir: "ltr",
    top: "30%",
    right: "3%",
    maxWidth: "220px",
    fontSize: "0.82rem",
    opacity: 0.72,
    floatDuration: 4.3,
    floatDelay: 0.9,
    staggerDelay: 600,
  },
  {
    text: "O que a Bíblia diz sobre a graça?",
    lang: "pt",
    dir: "ltr",
    top: "68%",
    left: "3%",
    maxWidth: "200px",
    fontSize: "0.78rem",
    opacity: 0.6,
    floatDuration: 3.8,
    floatDelay: 0.5,
    staggerDelay: 750,
  },
  {
    text: "Что говорит Библия о надежде?",
    lang: "ru",
    dir: "ltr",
    top: "65%",
    right: "2%",
    maxWidth: "225px",
    fontSize: "0.80rem",
    opacity: 0.68,
    floatDuration: 4.5,
    floatDelay: 1.4,
    staggerDelay: 900,
  },
  {
    text: "圣经怎么说关于智慧？",
    lang: "zh",
    dir: "ltr",
    top: "82%",
    left: "5%",
    maxWidth: "160px",
    fontSize: "0.88rem",
    opacity: 0.8,
    floatDuration: 3.0,
    floatDelay: 0.2,
    staggerDelay: 1050,
  },
  {
    text: "प्यार के बारे में बाइबल क्या कहती है?",
    lang: "hi",
    dir: "ltr",
    top: "87%",
    left: "30%",
    maxWidth: "min(220px,45vw)",
    fontSize: "0.78rem",
    opacity: 0.58,
    floatDuration: 4.2,
    floatDelay: 0.8,
    staggerDelay: 1200,
  },
  {
    text: "성경은 용서에 대해 뭐라고 하나요?",
    lang: "ko",
    dir: "ltr",
    top: "80%",
    right: "4%",
    maxWidth: "200px",
    fontSize: "0.82rem",
    opacity: 0.72,
    floatDuration: 3.6,
    floatDelay: 1.2,
    staggerDelay: 1350,
  },
  {
    text: "ماذا يقول الكتاب المقدس عن الصلاة؟",
    lang: "ar",
    dir: "rtl",
    top: "14%",
    right: "22%",
    maxWidth: "min(210px,45vw)",
    fontSize: "0.80rem",
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
          "linear-gradient(160deg, #3a5f96 0%, #4A6FA5 50%, #5a7fb5 100%)",
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
        {/* Cross icon */}
        <div className="mb-6 opacity-90">
          <svg
            width="56"
            height="56"
            viewBox="0 0 56 56"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
            aria-hidden="true"
          >
            <rect x="22" y="4" width="12" height="48" rx="3" fill="white" />
            <rect x="4" y="18" width="48" height="12" rx="3" fill="white" />
          </svg>
        </div>

        <h1 className="text-white text-2xl font-semibold mb-2 tracking-wide">
          Bible Inspiration
        </h1>
        <p className="text-white/60 text-sm tracking-wider uppercase">
          Find encouragement through Scripture
        </p>
      </div>
    </div>
  );
}
