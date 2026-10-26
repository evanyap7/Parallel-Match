import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { en, type Key, type Messages } from "./en";

export type { Key, Messages };
export type Params = Record<string, string | number>;
export type T = (key: Key, params?: Params) => string;

export interface Locale {
  code: string;
  /** The language's own name, shown in the picker. */
  name: string;
  dir: "ltr" | "rtl";
  load: () => Promise<Messages>;
}

const pick = (p: Promise<Record<string, Messages>>, name: string) =>
  p.then((m) => m[name]);

/** Football is played in all of these: the Americas, Europe, the Middle East and Asia. */
export const LOCALES: Locale[] = [
  { code: "en", name: "English", dir: "ltr", load: async () => en },
  { code: "es", name: "Español", dir: "ltr", load: () => pick(import("./locales/es"), "es") },
  { code: "pt", name: "Português", dir: "ltr", load: () => pick(import("./locales/pt"), "pt") },
  { code: "fr", name: "Français", dir: "ltr", load: () => pick(import("./locales/fr"), "fr") },
  { code: "de", name: "Deutsch", dir: "ltr", load: () => pick(import("./locales/de"), "de") },
  { code: "it", name: "Italiano", dir: "ltr", load: () => pick(import("./locales/it"), "it") },
  { code: "nl", name: "Nederlands", dir: "ltr", load: () => pick(import("./locales/nl"), "nl") },
  { code: "pl", name: "Polski", dir: "ltr", load: () => pick(import("./locales/pl"), "pl") },
  { code: "ru", name: "Русский", dir: "ltr", load: () => pick(import("./locales/ru"), "ru") },
  { code: "tr", name: "Türkçe", dir: "ltr", load: () => pick(import("./locales/tr"), "tr") },
  { code: "ar", name: "العربية", dir: "rtl", load: () => pick(import("./locales/ar"), "ar") },
  { code: "hi", name: "हिन्दी", dir: "ltr", load: () => pick(import("./locales/hi"), "hi") },
  { code: "id", name: "Bahasa Indonesia", dir: "ltr", load: () => pick(import("./locales/id"), "id") },
  { code: "th", name: "ไทย", dir: "ltr", load: () => pick(import("./locales/th"), "th") },
  { code: "vi", name: "Tiếng Việt", dir: "ltr", load: () => pick(import("./locales/vi"), "vi") },
  { code: "zh", name: "中文（简体）", dir: "ltr", load: () => pick(import("./locales/zh"), "zh") },
  { code: "ja", name: "日本語", dir: "ltr", load: () => pick(import("./locales/ja"), "ja") },
  { code: "ko", name: "한국어", dir: "ltr", load: () => pick(import("./locales/ko"), "ko") },
];

const STORAGE_KEY = "pm-lang";
const known = (code: string | null | undefined) =>
  LOCALES.find((l) => l.code === code);

export function fill(template: string, params?: Params) {
  return params
    ? template.replace(/\{(\w+)\}/g, (m, k) =>
        k in params ? String(params[k]) : m,
      )
    : template;
}

export function makeT(messages: Messages): T {
  return (key, params) => fill(messages[key] ?? en[key], params);
}

/** English translator, the default for pure helpers and tests. */
export const tEn: T = makeT(en);

/** Like `t`, but params may be React nodes (for bold figures inside a sentence). */
export function rich(
  messages: Messages,
  key: Key,
  params: Record<string, ReactNode>,
): ReactNode[] {
  return (messages[key] ?? en[key]).split(/(\{\w+\})/).map((part, i) => {
    const name = /^\{(\w+)\}$/.exec(part)?.[1];
    return name && name in params ? (
      <span key={i}>{params[name]}</span>
    ) : (
      part
    );
  });
}

/** Saved choice, else the browser's language, else English. */
export function initialLang(): string {
  try {
    const saved = known(localStorage.getItem(STORAGE_KEY));
    if (saved) return saved.code;
  } catch {
    // storage can be blocked; fall through to the browser language
  }
  for (const tag of navigator.languages ?? [navigator.language]) {
    const hit = known(tag?.toLowerCase().split("-")[0]);
    if (hit) return hit.code;
  }
  return "en";
}

interface I18n {
  lang: string;
  dir: "ltr" | "rtl";
  t: T;
  r: (key: Key, params: Record<string, ReactNode>) => ReactNode[];
  setLang: (code: string) => void;
}

const Context = createContext<I18n>({
  lang: "en",
  dir: "ltr",
  t: tEn,
  r: (key, params) => rich(en, key, params),
  setLang: () => {},
});

export const useI18n = () => useContext(Context);

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState(initialLang);
  const [messages, setMessages] = useState<Messages>(en);
  const locale = known(lang) ?? LOCALES[0];

  useEffect(() => {
    let live = true;
    locale
      .load()
      .then((m) => live && setMessages(m))
      .catch(() => live && setMessages(en));
    return () => {
      live = false;
    };
  }, [locale]);

  useEffect(() => {
    document.documentElement.lang = locale.code;
    document.documentElement.dir = locale.dir;
  }, [locale]);

  const setLang = useCallback((code: string) => {
    const next = known(code);
    if (!next) return;
    setLangState(next.code);
    try {
      localStorage.setItem(STORAGE_KEY, next.code);
    } catch {
      // not persisted; the choice still applies for this visit
    }
  }, []);

  const value = useMemo<I18n>(
    () => ({
      lang: locale.code,
      dir: locale.dir,
      t: makeT(messages),
      r: (key, params) => rich(messages, key, params),
      setLang,
    }),
    [locale, messages, setLang],
  );
  return <Context.Provider value={value}>{children}</Context.Provider>;
}
