"use client";

import { FormEvent, useCallback, useState } from "react";
import {
  InsightsResponse,
  fetchInsights,
  parseCv,
  suggestLocations,
  suggestRoles,
} from "@/lib/api";
import { InsightsPanel } from "@/components/InsightsPanel";
import { Typeahead } from "@/components/Typeahead";

export default function HomePage() {
  const [query, setQuery] = useState("");
  const [location, setLocation] = useState("");
  const [cvSkills, setCvSkills] = useState<string[]>([]);
  const [cvText, setCvText] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [insights, setInsights] = useState<InsightsResponse | null>(null);
  const [hasCvInput, setHasCvInput] = useState(false);

  const loadRoles = useCallback((q: string) => suggestRoles(q), []);
  const loadLocations = useCallback((q: string) => suggestLocations(q), []);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const skillsFromText = cvText
        .split(/[,;\n]/)
        .map((s) => s.trim())
        .filter(Boolean);
      const merged = Array.from(new Set([...cvSkills, ...skillsFromText]));
      const data = await fetchInsights({
        query,
        location,
        cv_skills: merged,
      });
      setHasCvInput(merged.length > 0);
      setInsights(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  async function onCvUpload(file: File | null) {
    if (!file) return;
    setError(null);
    try {
      const skills = await parseCv(file);
      setCvSkills(skills);
      setCvText(skills.join(", "));
    } catch (err) {
      setError(err instanceof Error ? err.message : "CV parse failed");
    }
  }

  return (
    <main className="relative z-10 mx-auto min-h-screen max-w-5xl px-5 pb-20 pt-10 sm:px-8">
      <header className="mb-12 flex items-baseline justify-between gap-4">
        <p className="text-xl font-semibold tracking-tight text-[var(--ink)]">lernyra</p>
        <p className="hidden text-sm text-[var(--muted)] sm:block">
          Jobs, skills, and what to learn next
        </p>
      </header>

      <section className="rounded-2xl border border-[var(--line)] bg-[var(--surface)] px-6 py-9 sm:px-9 sm:py-11">
        <h1 className="max-w-xl text-3xl font-semibold leading-tight tracking-tight text-[var(--ink)] sm:text-4xl">
          See what a role needs — and what to learn next
        </h1>
        <p className="mt-3 max-w-lg text-[15px] leading-relaxed text-[var(--muted)] sm:text-base">
          Pick a position to get typical requirements, then books, courses, and a
          study roadmap. Optionally compare against your CV.
        </p>

        <form onSubmit={onSubmit} className="relative mt-8 space-y-4">
          <div className="grid gap-3 sm:grid-cols-[1.4fr_1fr_auto]">
            <Typeahead
              label="Role"
              value={query}
              onChange={setQuery}
              fetchSuggestions={loadRoles}
              placeholder="e.g. Software Engineer"
              required
            />
            <Typeahead
              label="Location"
              value={location}
              onChange={setLocation}
              fetchSuggestions={loadLocations}
              placeholder="Remote, Berlin…"
              footerHint="Type to narrow cities worldwide"
            />
            <div className="flex items-end">
              <button
                type="submit"
                disabled={loading || !query.trim()}
                className="w-full rounded-xl bg-[var(--ink)] px-5 py-2.5 text-[15px] font-medium text-white transition hover:opacity-90 disabled:opacity-50 sm:w-auto"
              >
                {loading ? "Analyzing…" : "Get insights"}
              </button>
            </div>
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <label className="block">
              <span className="mb-1.5 block text-sm text-[var(--muted)]">
                Your skills (comma-separated)
              </span>
              <textarea
                value={cvText}
                onChange={(e) => setCvText(e.target.value)}
                rows={3}
                placeholder="React, TypeScript, Node.js…"
                className="w-full resize-y rounded-xl border border-[var(--line)] bg-white px-3.5 py-2.5 text-[15px] text-[var(--ink)] outline-none transition focus:border-[var(--accent)] focus:ring-2 focus:ring-[var(--accent-soft)]"
              />
            </label>
            <label className="block">
              <span className="mb-1.5 block text-sm text-[var(--muted)]">
                Or upload CV (PDF / TXT / DOC)
              </span>
              <div className="flex min-h-[5.5rem] items-center rounded-xl border border-dashed border-[var(--line)] bg-[var(--surface-soft)] px-4">
                <input
                  type="file"
                  accept=".pdf,.txt,application/pdf,text/plain"
                  onChange={(e) => onCvUpload(e.target.files?.[0] ?? null)}
                  className="w-full text-sm text-[var(--muted)] file:mr-3 file:rounded-lg file:border-0 file:bg-[var(--ink)] file:px-3 file:py-2 file:text-sm file:font-medium file:text-white"
                />
              </div>
            </label>
          </div>
        </form>

        {error && (
          <p className="mt-4 rounded-xl bg-[#f8eee6] px-4 py-3 text-sm text-[var(--warn)]">
            {error}
          </p>
        )}
      </section>

      {insights && (
        <div className="animate-fade mt-12">
          <InsightsPanel data={insights} showCvGaps={hasCvInput} />
        </div>
      )}
    </main>
  );
}
