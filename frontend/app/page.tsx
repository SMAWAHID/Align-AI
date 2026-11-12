import Link from "next/link";
import {
  ArrowRight,
  Cpu,
  FileText,
  Github,
  Layers,
  Lock,
  ScanSearch,
  Sparkles,
  Target,
} from "lucide-react";

export const metadata = {
  title: "AlignAI — Semantic Resume Matcher",
  description:
    "Score your resume against any job description, see exactly which skills are missing, and get an ATS-optimised rewrite back.",
};

const PIPELINE = [
  { icon: FileText, title: "Extract", body: "PDF, DOCX or plain text is parsed in memory. Nothing is written to disk." },
  { icon: ScanSearch, title: "Embed", body: "Resume and job description become 1024-dimension vectors." },
  { icon: Target, title: "Score", body: "Cosine similarity, weighted 60/40 against literal keyword overlap." },
  { icon: Layers, title: "Analyse", body: "An LLM names the missing skills and where to learn each one." },
  { icon: Sparkles, title: "Rewrite", body: "You get an ATS-friendly resume back as PDF, Word, Markdown or text." },
];

const SYNE = { fontFamily: "'Syne', sans-serif" } as const;

export default function LandingPage() {
  return (
    <div className="min-h-dvh flex flex-col">
      {/* Nav */}
      <header className="sticky top-0 z-50 border-b border-white/[0.06] backdrop-blur-xl bg-[#08090e]/80">
        <div className="max-w-6xl mx-auto px-6 h-14 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center shadow-lg shadow-indigo-500/30">
              <Cpu size={14} className="text-white" />
            </div>
            <span className="font-bold text-white tracking-tight" style={{ ...SYNE, fontSize: "1.05rem" }}>
              AlignAI
            </span>
          </div>
          <nav className="flex items-center gap-5">
            <a
              href="https://github.com/SMAWAHID/Align-AI"
              target="_blank"
              rel="noopener noreferrer"
              className="text-white/30 hover:text-white/60 transition-colors"
              aria-label="Source on GitHub"
            >
              <Github size={17} />
            </a>
            <Link href="/login" className="text-sm text-white/50 hover:text-white transition-colors">
              Sign in
            </Link>
            <Link
              href="/signup"
              className="text-sm font-semibold text-white bg-white/[0.07] hover:bg-white/[0.12] border border-white/10 rounded-lg px-3.5 py-1.5 transition-colors"
            >
              Get started
            </Link>
          </nav>
        </div>
      </header>

      {/* Hero */}
      <section className="px-6 pt-20 pb-16 text-center">
        <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-indigo-500/10 border border-indigo-500/20 text-indigo-300 text-xs font-medium mb-7">
          <Sparkles size={12} />
          Semantic scoring, not keyword counting
        </div>

        <h1
          className="mx-auto max-w-3xl text-4xl sm:text-5xl lg:text-6xl font-bold text-white leading-[1.08] tracking-tight text-balance"
          style={SYNE}
        >
          Find out why your resume
          <span className="block bg-gradient-to-r from-indigo-400 via-violet-400 to-fuchsia-400 bg-clip-text text-transparent">
            keeps getting filtered out
          </span>
        </h1>

        <p className="mx-auto mt-6 max-w-xl text-base sm:text-lg text-white/45 leading-relaxed">
          Paste a job description, upload your resume, and get a match score backed by real
          semantic similarity — plus the specific skills you are missing and an ATS-optimised
          rewrite you can download.
        </p>

        <div className="mt-9 flex flex-col sm:flex-row items-center justify-center gap-3">
          <Link
            href="/signup"
            className="w-full sm:w-auto h-11 px-6 rounded-lg bg-gradient-to-br from-indigo-500 to-violet-600 text-white text-sm font-semibold inline-flex items-center justify-center gap-2 shadow-lg shadow-indigo-500/25 hover:opacity-90 transition-opacity"
          >
            Analyse my resume
            <ArrowRight size={15} />
          </Link>
          <Link
            href="/login"
            className="w-full sm:w-auto h-11 px-6 rounded-lg border border-white/10 bg-white/[0.03] text-white/70 text-sm font-semibold inline-flex items-center justify-center hover:bg-white/[0.06] hover:text-white transition-colors"
          >
            I already have an account
          </Link>
        </div>

        <p className="mt-5 text-xs text-white/25">Free · no card · your files are never stored</p>
      </section>

      {/* Pipeline — numbered because these steps genuinely run in order */}
      <section className="px-6 pb-20">
        <div className="max-w-5xl mx-auto">
          <h2
            className="text-center text-xs font-medium uppercase tracking-[0.16em] text-white/30 mb-9"
            style={SYNE}
          >
            What happens when you hit analyse
          </h2>

          <ol className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
            {PIPELINE.map(({ icon: Icon, title, body }, i) => (
              <li
                key={title}
                className="rounded-xl border border-white/[0.07] bg-white/[0.02] p-4 flex flex-col gap-2.5"
              >
                <div className="flex items-center gap-2">
                  <div className="w-7 h-7 rounded-lg bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center">
                    <Icon size={13} className="text-indigo-300" />
                  </div>
                  <span className="text-[10px] font-mono text-white/25 tabular-nums">
                    {String(i + 1).padStart(2, "0")}
                  </span>
                </div>
                <h3 className="text-sm font-semibold text-white/90">{title}</h3>
                <p className="text-xs text-white/40 leading-relaxed">{body}</p>
              </li>
            ))}
          </ol>
        </div>
      </section>

      {/* Privacy */}
      <section className="px-6 pb-24">
        <div className="max-w-3xl mx-auto rounded-2xl border border-white/[0.07] bg-white/[0.02] p-7 sm:p-9">
          <div className="flex items-start gap-4">
            <div className="w-9 h-9 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center shrink-0">
              <Lock size={16} className="text-emerald-300" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-white mb-2" style={SYNE}>
                Your analyses belong to you
              </h2>
              <p className="text-sm text-white/45 leading-relaxed">
                Every result is tied to your account, and history queries are filtered by owner —
                nobody else can list, open or delete your analyses. Uploaded files are parsed in
                memory and discarded; only the scores, the gap report and your rewritten resume
                are stored.
              </p>
            </div>
          </div>
        </div>
      </section>

      <footer className="mt-auto border-t border-white/[0.06] px-6 py-6">
        <div className="max-w-6xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-3 text-xs text-white/25">
          <span>AlignAI · Next.js + FastAPI + PostgreSQL · Jina embeddings, Groq inference</span>
          <a
            href="https://github.com/SMAWAHID/Align-AI"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-white/50 transition-colors"
          >
            Source on GitHub
          </a>
        </div>
      </footer>
    </div>
  );
}
