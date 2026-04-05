import ReactMarkdown from "react-markdown";

interface LegalDocumentProps {
  markdown: string;
}

export default function LegalDocument({ markdown }: LegalDocumentProps) {
  return (
    <div className="min-h-screen px-4 py-10 sm:px-6 lg:px-8">
      <article className="mx-auto w-full max-w-3xl rounded-2xl border border-gray-200 bg-white p-6 shadow-sm sm:p-8">
        <div className="legal-markdown text-gray-900">
          <ReactMarkdown>{markdown}</ReactMarkdown>
        </div>
      </article>
    </div>
  );
}
