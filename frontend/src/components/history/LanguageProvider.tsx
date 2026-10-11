"use client";
import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import type { Language } from "@/lib/history";
import { dictionaries, english, languageNames, type CopyKey, type Dictionary } from "@/lib/historyLanguage";
const Context = createContext<{ language: Language; dictionary: Dictionary; setLanguage: (language: Language) => void; t: (key: CopyKey) => string }>({ language:"en", dictionary:english, setLanguage: () => {}, t: key => english[key] });
export function LanguageProvider({ language, dictionary, children }: { language: Language; dictionary: Dictionary; children: ReactNode }) {
  const [selected, setSelected] = useState(language);
  const activeDictionary = selected === language ? dictionary : dictionaries[selected];
  const t = useCallback((key: CopyKey) => activeDictionary[key], [activeDictionary]);
  const setLanguage = useCallback((value: Language) => { setSelected(value); document.documentElement.lang = value; }, []);
  const value = useMemo(() => ({ language: selected, dictionary: activeDictionary, setLanguage, t }), [selected, activeDictionary, setLanguage, t]);
  return <Context.Provider value={value}>{children}</Context.Provider>;
}
export function useLanguage() { return useContext(Context); }
export function LanguageSelector() {
  const { language, t, setLanguage } = useLanguage();
  const router = useRouter();
  return <div className="flex flex-col gap-2"><label>{t("language")}<select className="ml-2 rounded border p-2" value={language} onChange={e => { document.cookie = `history_language=${e.target.value}; Path=/; SameSite=Lax; Max-Age=31536000${location.protocol === "https:" ? "; Secure" : ""}`; setLanguage(e.target.value as Language); router.refresh(); }}>{Object.entries(languageNames).map(([key,name]) => <option key={key} value={key}>{name}</option>)}</select></label>{language !== "en" && <p className="text-xs text-grey-600">{t("pilot")}<span lang="en" className="block">Untranslated content remains in English. Original job messages retain their source language.</span></p>}</div>;
}
