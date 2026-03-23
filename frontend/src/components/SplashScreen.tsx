"use client";

import { useState, useEffect, useCallback } from "react";
import { warmupBackend } from "@/lib/api";

const QUESTIONS = [
  { text: "What does the Bible say about love?", lang: "en", dir: "ltr" },
  { text: "Cosa dice la Bibbia sul perdono?", lang: "it", dir: "ltr" },
  { text: "¿Qué dice la Biblia sobre la esperanza?", lang: "es", dir: "ltr" },
  { text: "Was sagt die Bibel über Frieden?", lang: "de", dir: "ltr" },
  { text: "Que dit la Bible sur la foi?", lang: "fr", dir: "ltr" },
  { text: "O que a Bíblia diz sobre a graça?", lang: "pt", dir: "ltr" },
  { text: "Что говорит Библия о надежде?", lang: "ru", dir: "ltr" },
  { text: "圣经怎么说关于智慧？", lang: "zh", dir: "ltr" },
  { text: "प्यार के बारे में बाइबल क्या कहती है?", lang: "hi", dir: "ltr" },
  { text: "성경은 용서에 대해 뭐라고 하나요?", lang: "ko", dir: "ltr" },
  { text: "ماذا يقول الكتاب المقدس عن الصلاة؟", lang: "ar", dir: "rtl" },
];

const PHRASE_INTERVAL_MS = 2200;
const PHRASE_FADE_MS = 500;
const SPLASH_DURATION_MS = 4200;
const SPLASH_EXIT_MS = 700;

interface SplashScreenProps {
  onComplete: () => void;
}

export function SplashScreen({ onComplete }: SplashScreenProps) {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [phraseVisible, setPhraseVisible] = useState(true);
  const [exiting, setExiting] = useState(false);

  const handleComplete = useCallback(onComplete, [onComplete]);

  useEffect(() => {
    // Pre-warm backend during splash
    warmupBackend(
      () => {},
      () => {},
    );

    let nextIndex = 1;

    // Cycle phrases
    const cyclePhrase = () => {
      setPhraseVisible(false);
      const fadeTimer = setTimeout(() => {
        setCurrentIndex(nextIndex % QUESTIONS.length);
        nextIndex++;
        setPhraseVisible(true);
      }, PHRASE_FADE_MS);
      return fadeTimer;
    };

    const fadeTimers: ReturnType<typeof setTimeout>[] = [];
    const intervalId = setInterval(() => {
      fadeTimers.push(cyclePhrase());
    }, PHRASE_INTERVAL_MS);

    // Begin exit sequence after splash duration
    const exitTimer = setTimeout(() => {
      clearInterval(intervalId);
      setExiting(true);
      setTimeout(handleComplete, SPLASH_EXIT_MS);
    }, SPLASH_DURATION_MS);

    return () => {
      clearInterval(intervalId);
      clearTimeout(exitTimer);
      fadeTimers.forEach(clearTimeout);
    };
  }, [handleComplete]);

  const question = QUESTIONS[currentIndex];

  return (
    <div
      className="fixed inset-0 z-50 flex flex-col items-center justify-center"
      style={{
        background:
          "linear-gradient(160deg, #3a5f96 0%, #4A6FA5 50%, #5a7fb5 100%)",
        opacity: exiting ? 0 : 1,
        transition: `opacity ${SPLASH_EXIT_MS}ms ease-out`,
        pointerEvents: exiting ? "none" : "auto",
      }}
      aria-hidden="true"
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

      {/* App title */}
      <h1 className="text-white text-2xl font-semibold mb-2 tracking-wide">
        Bible Inspiration
      </h1>
      <p className="text-white/60 text-sm mb-14 tracking-wider uppercase">
        Find encouragement through Scripture
      </p>

      {/* Cycling question */}
      <div
        className="max-w-sm px-8 text-center"
        style={{
          opacity: phraseVisible ? 1 : 0,
          transform: phraseVisible ? "translateY(0)" : "translateY(8px)",
          transition: `opacity ${PHRASE_FADE_MS}ms ease-in-out, transform ${PHRASE_FADE_MS}ms ease-in-out`,
        }}
        dir={question.dir}
        lang={question.lang}
      >
        <p className="text-white/90 text-lg italic leading-relaxed">
          &ldquo;{question.text}&rdquo;
        </p>
      </div>

      {/* Progress dots */}
      <div className="flex gap-1.5 mt-10">
        {QUESTIONS.map((_, i) => (
          <div
            key={i}
            className="rounded-full transition-all duration-300"
            style={{
              width: i === currentIndex ? "20px" : "6px",
              height: "6px",
              backgroundColor:
                i === currentIndex
                  ? "rgba(255,255,255,0.9)"
                  : "rgba(255,255,255,0.35)",
            }}
          />
        ))}
      </div>
    </div>
  );
}
