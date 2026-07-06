"use client";

/**
 * Root global error boundary (BITB-066).
 *
 * Next.js renders this when an error is thrown in the root layout — the one
 * place the in-tree <ErrorBoundary> component cannot catch. It must render its
 * own <html>/<body>. Besides showing a minimal fallback, it reports the error
 * so a root-layout crash is observable client-side.
 */

import { useEffect } from "react";
import { reportClientError } from "@/lib/clientErrorReporter";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    reportClientError("react_render", error.stack || error.message);
  }, [error]);

  return (
    <html lang="en">
      <body
        style={{
          minHeight: "100vh",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontFamily: "system-ui, sans-serif",
          padding: "1rem",
          textAlign: "center",
        }}
      >
        <div>
          <h1 style={{ fontSize: "1.5rem", marginBottom: "0.5rem" }}>
            Something went wrong
          </h1>
          <p style={{ color: "#555", marginBottom: "1.5rem" }}>
            Please try again in a moment.
          </p>
          <button
            onClick={() => reset()}
            style={{
              padding: "0.75rem 1.5rem",
              borderRadius: "0.5rem",
              border: "none",
              background: "#4f46e5",
              color: "white",
              cursor: "pointer",
            }}
          >
            Try again
          </button>
        </div>
      </body>
    </html>
  );
}
