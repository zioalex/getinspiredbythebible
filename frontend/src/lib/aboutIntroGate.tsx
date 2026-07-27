"use client";

import { createContext, useContext } from "react";

// Coordinates AboutIntroModal (BITB-077) and WhatsNewModal so they never
// compete for the same page load. "pending" until Providers has checked the
// splash-done + localStorage state; "show-intro" for the rest of the session
// once the intro modal has been chosen (even after it's dismissed — What's
// New is deferred to the next visit, not the next state change); "clear"
// when there is nothing for the intro modal to show.
export type AboutIntroGateState = "pending" | "show-intro" | "clear";

const AboutIntroGateContext = createContext<AboutIntroGateState>("pending");

export const AboutIntroGateProvider = AboutIntroGateContext.Provider;

export function useAboutIntroGate(): AboutIntroGateState {
  return useContext(AboutIntroGateContext);
}
