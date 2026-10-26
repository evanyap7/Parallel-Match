import { useEffect, useRef } from "react";
import { GitBranch } from "lucide-react";
import { LOCALES, suggestedLang, useI18n } from "../i18n";

/** Shown before anything else: the fan picks the language of the whole app,
    including the agents' commentary, then enters. */
export function LanguageGate() {
  const { setLang } = useI18n();
  const suggested = useRef(suggestedLang()).current;
  const first = useRef<HTMLButtonElement>(null);
  useEffect(() => first.current?.focus(), []);
  return (
    <main className="lang-gate" id="main">
      <section role="dialog" aria-modal="true" aria-labelledby="gate-title">
        <p className="gate-brand">
          <GitBranch size={20} aria-hidden="true" /> Parallel Match
        </p>
        <h1 id="gate-title">Choose your language</h1>
        <p className="gate-sub" lang="mul">
          Elige tu idioma · Choisissez votre langue · Wähle deine Sprache ·
          选择语言 · 言語を選択 · اختر لغتك
        </p>
        <ul>
          {LOCALES.map((l) => (
            <li key={l.code}>
              <button
                ref={l.code === suggested ? first : undefined}
                lang={l.code}
                dir={l.dir}
                className={l.code === suggested ? "suggested" : ""}
                onClick={() => setLang(l.code)}
              >
                {l.name}
              </button>
            </li>
          ))}
        </ul>
        <p className="gate-note">
          The interface and the commentary will use this language. You can
          change it any time from the top bar.
        </p>
      </section>
    </main>
  );
}
