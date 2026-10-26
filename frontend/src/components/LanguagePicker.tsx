import { Languages } from "lucide-react";
import { LOCALES, useI18n } from "../i18n";

/** Each language is named in itself, so a reader can find theirs in any UI language. */
export function LanguagePicker() {
  const { lang, setLang, t } = useI18n();
  return (
    <label className="lang-picker">
      <Languages size={16} aria-hidden="true" />
      <span className="sr-only">{t("lang.label")}</span>
      <select value={lang} onChange={(e) => setLang(e.target.value)}>
        {LOCALES.map((l) => (
          <option key={l.code} value={l.code} lang={l.code}>
            {l.name}
          </option>
        ))}
      </select>
    </label>
  );
}
