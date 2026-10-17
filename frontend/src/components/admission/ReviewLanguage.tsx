"use client";
/** Scoped typed review copy; candidates need native review. Language changes never remount forms. */
import { createContext, useContext, useState, type ReactNode } from "react";
type Language = "en" | "yo" | "ha" | "ig";
const rows = {
  pending: [
    "Your review is pending.",
    "Àyẹ̀wò rẹ ń dúró.",
    "Ana jiran bitar ku.",
    "Nyocha gị ka na-eche.",
  ],
  policyType: [
    "Onboarding policy",
    "Ìlànà ìbẹ̀rẹ̀",
    "Manufar shiga",
    "Usoro nnabata",
  ],
  generic: ["General work", "Iṣẹ́ gbogbogbò", "Aikin gaba ɗaya", "Ọrụ izugbe"],
  domestic: ["Domestic work", "Iṣẹ́ ilé", "Aikin gida", "Ọrụ ụlọ"],
  ride_hailing: ["Ride hailing", "Iṣẹ́ awakọ̀", "Aikin sufuri", "Ọrụ njem"],
  loading: [
    "Loading verification…",
    "A ń kó ìṣàyẹ̀wò…",
    "Ana loda tantancewa…",
    "Na-ebunye nyocha…",
  ],
  ownership_approved: [
    "Ownership reviewed; history unverified",
    "A ṣàyẹ̀wò ẹni tó ni í; a kò tíì jẹ́rìí ìtàn",
    "An duba mallaka; ba a tabbatar da tarihi ba",
    "A nyochara onye nwe ya; a chọpụtabeghị akụkọ",
  ],
  completed: [
    "Completed (claimed)",
    "Ó parí (ìsọ)",
    "An gama (da'awa)",
    "Emechara (nkwupụta)",
  ],
  cancelled: [
    "Cancelled (claimed)",
    "A fagilé (ìsọ)",
    "An soke (da'awa)",
    "Akagbuola (nkwupụta)",
  ],
  no_show: [
    "No show (claimed)",
    "Kò wá (ìsọ)",
    "Bai halarta ba (da'awa)",
    "Abịaghị (nkwupụta)",
  ],
  unknown: ["Unknown", "A kò mọ̀", "Ba a sani ba", "Amaghị"],
  supporting_information: [
    "Reply to the reviewer with the requested information",
    "Dá olùṣàyẹ̀wò lóhùn pẹ̀lú àlàyé tí a béèrè",
    "Amsa wa mai bita da bayanin da aka nema",
    "Zaa onye nyocha na ozi a rịọrọ",
  ],
  disabled: [
    "This pilot workflow is not enabled.",
    "A kò tíì ṣí ìlànà ìdánwò yìí.",
    "Ba a kunna wannan tsarin gwaji ba.",
    "Emebeghị usoro nnwale a.",
  ],
  platform: [
    "Reviewing platform",
    "Pẹpẹ àyẹ̀wò",
    "Dandalin bita",
    "Ikpo okwu nyocha",
  ],
  ourPlatform: ["Our platform", "Pẹpẹ wa", "Dandalinmu", "Ikpo okwu anyị"],
  newImport: [
    "Start another import",
    "Bẹ̀rẹ̀ àkọsílẹ̀ tuntun",
    "Fara wani shigo da bayanai",
    "Malite ndekọ ọzọ",
  ],
  verification: [
    "Additional verification",
    "Ìṣàyẹ̀wò àfikún",
    "Ƙarin tantancewa",
    "Nnyocha ọzọ",
  ],
  signed: [
    "Signed credential",
    "Àkọsílẹ̀ tí a fọwọ́ sí",
    "Shaida mai sa hannu",
    "Asambodo mbinye aka",
  ],
  unsigned: [
    "Unsigned history",
    "Ìtàn iṣẹ́ tí a kò fọwọ́ sí",
    "Tarihin aiki marar sa hannu",
    "Akụkọ ọrụ na-enweghị mbinye aka",
  ],
  language: ["Language", "Èdè", "Harshe", "Asụsụ"],
  candidate: [
    "Candidate translations; native review pending. Missing copy stays in English.",
    "Ìtumọ̀ ìdánwò; àyẹ̀wò olùsọ èdè ṣì kù. Ọ̀rọ̀ tí kò sí yóò wà ní Gẹ̀ẹ́sì.",
    "Fassarar gwaji; ana jiran bitar masu harshen. Abin da bai samu ba yana Turanci.",
    "Ntụgharị nnwale; a na-eche nyocha ndị na-asụ asụsụ. Ozi na-adịghị ga-anọ na Bekee.",
  ],
  csv: [
    "Work-history CSV",
    "CSV ìtàn iṣẹ́",
    "CSV tarihin aiki",
    "CSV akụkọ ọrụ",
  ],
  document: [
    "Supporting PDF, JPEG or PNG",
    "Ìwé ìtìlẹ́yìn PDF, JPEG tàbí PNG",
    "Takardar shaida PDF, JPEG ko PNG",
    "Akwụkwọ nkwado PDF, JPEG ma ọ bụ PNG",
  ],
  source: [
    "Source of this history",
    "Orísun ìtàn yìí",
    "Tushen wannan tarihin",
    "Ebe akụkọ a si bịa",
  ],
  template: [
    "Download CSV template",
    "Gba àpẹẹrẹ CSV",
    "Sauke samfurin CSV",
    "Budata ihe atụ CSV",
  ],
  preview: [
    "Prepare preview",
    "Ṣètò àwòtẹ́lẹ̀",
    "Shirya samfoti",
    "Kwadebe nlele",
  ],
  submit: [
    "Submit for ownership review",
    "Fi ránṣẹ́ fún àyẹ̀wò ẹni tó ni í",
    "Aika don nazarin mallaka",
    "Ziga maka nyocha onye nwe ya",
  ],
  refresh: [
    "Refresh / retry",
    "Túnṣe / gbìyànjú",
    "Sabunta / sake gwadawa",
    "Megharịa / gbalịa ọzọ",
  ],
  reconcile: [
    "Check submission status",
    "Ṣàyẹ̀wò ipò ìfiránṣẹ́",
    "Duba matsayin aikawa",
    "Lelee ọnọdụ nzipu",
  ],
  busy: ["Please wait…", "Jọ̀wọ́ dúró…", "A jira…", "Biko chere…"],
  note: [
    "Unsigned evidence is not verified work. Ownership review can affect only a separate provisional rating.",
    "Ẹ̀rí tí a kò fọwọ́ sí kì í ṣe iṣẹ́ tí a ti jẹ́rìí. Àyẹ̀wò ẹni tó ni í kan ìwọ̀n àkọ́kọ́ ọ̀tọ̀ nìkan.",
    "Shaidar marar sa hannu ba aikin da aka tabbatar ba ce. Bitar mallaka tana shafar kimar farko dabam kawai.",
    "Ihe akaebe na-enweghị mbinye aka abụghị ọrụ e nyochara. Nnyocha onye nwe ya na-emetụta naanị akara mbido dị iche.",
  ],
  retention: [
    "Files are private and retained for up to 30 days after review; unreviewed submissions expire after 30 days.",
    "Àwọn fáìlì jẹ́ àṣírí, a sì pa wọ́n mọ́ títí ọjọ́ 30 lẹ́yìn àyẹ̀wò; èyí tí a kò ṣàyẹ̀wò dópin lẹ́yìn ọjọ́ 30.",
    "Fayiloli na sirri ne har zuwa kwanaki 30 bayan bita; waɗanda ba a duba ba su ƙare bayan kwanaki 30.",
    "Faịlụ bụ nke nzuzo ruo ụbọchị 30 mgbe nyocha gasịrị; ndị a na-enyochabeghị na-agwụ mgbe ụbọchị 30 gasịrị.",
  ],
  consent: [
    "I confirm this history concerns me and consent to private ownership review.",
    "Mo jẹ́rìí pé ìtàn yìí jẹ́ tèmi, mo sì gba àyẹ̀wò àṣírí ẹni tó ni í.",
    "Na tabbatar wannan tarihin nawa ne kuma na amince da bitar mallaka ta sirri.",
    "Ekwenyere m na akụkọ a gbasara m ma kwenye nyocha nzuzo nke onye nwe ya.",
  ],
  withdraw: [
    "Withdraw evidence",
    "Yọ ẹ̀rí kúrò",
    "Janye shaida",
    "Wepụ ihe akaebe",
  ],
  replace: [
    "Submit corrected revision",
    "Fi àtúnṣe tuntun ránṣẹ́",
    "Aika gyaran sabon sigar",
    "Ziga ụdị e deziri",
  ],
  imports: [
    "Your import reviews",
    "Àyẹ̀wò àkọsílẹ̀ rẹ",
    "Bitar shigo da bayananka",
    "Nnyocha ndekọ gị",
  ],
  noImports: [
    "No unsigned imports yet.",
    "Kò sí àkọsílẹ̀ tí a kò fọwọ́ sí.",
    "Babu tarihin da aka shigo da shi tukuna.",
    "Enweghị ndekọ ọhụrụ ugbu a.",
  ],
  additional_verification: [
    "Complete identity and liveness verification",
    "Parí ìṣàyẹ̀wò ìdánimọ̀ àti pé o wà láàyè",
    "Kammala tantance shaida da kasancewa a raye",
    "Mechaa nyocha njirimara na ịdị ndụ",
  ],
  manual_review: [
    "Manual review required",
    "Àyẹ̀wò ènìyàn ṣe pàtàkì",
    "Ana bukatar bitar mutum",
    "A chọrọ nyocha mmadụ",
  ],
  limited: [
    "Limited onboarding approved",
    "A gba ìbẹ̀rẹ̀ tó ní ààlà",
    "An amince da shiga mai iyaka",
    "A kwadoro nnabata nwere oke",
  ],
  approved: ["Approved", "A ti gbà á", "An amince", "A kwadoro"],
  declined: ["Not approved", "A kò gbà á", "Ba a amince ba", "A kwadoghị"],
  caseSubmit: [
    "Request onboarding review",
    "Béèrè àyẹ̀wò ìbẹ̀rẹ̀",
    "Nemi bitar shiga",
    "Rịọ nyocha nnabata",
  ],
  identity: ["Identity", "Ìdánimọ̀", "Shaida", "Njirimara"],
  liveness: ["Liveness", "Ìwà láàyè", "Kasancewa a raye", "Ịdị ndụ"],
  preparing: ["Preparing", "A ń ṣètò", "Ana shiryawa", "Na-akwadebe"],
  submitted: [
    "Submitted for ownership review",
    "A ti fi ránṣẹ́ fún àyẹ̀wò",
    "An aika don bita",
    "E zigara maka nyocha",
  ],
  changes_requested: [
    "More information requested",
    "A béèrè àlàyé sí i",
    "An nemi ƙarin bayani",
    "A rịọrọ ozi ọzọ",
  ],
  rejected: [
    "Ownership not approved",
    "A kò gba ẹni tó ni í",
    "Ba a amince da mallaka ba",
    "A kwadoghị onye nwe ya",
  ],
  withdrawn: ["Withdrawn", "A ti yọ ọ́", "An janye", "E wepụrụ"],
  expired: ["Expired", "Ó ti dópin", "Ya ƙare", "Ọ gwụla"],
  provisional: [
    "Provisional rating (unverified)",
    "Ìwọ̀n àkọ́kọ́ (a kò jẹ́rìí)",
    "Kimar farko (ba a tabbatar ba)",
    "Akara mbido (a nyochabeghị)",
  ],
  jobs: [
    "Maximum active jobs",
    "Iye iṣẹ́ tó lè lọ lọ́wọ́",
    "Iyakacin ayyuka masu gudana",
    "Oke ọrụ na-aga",
  ],
  amount: [
    "Maximum job value",
    "Iye owó iṣẹ́ tó pọ̀ jù",
    "Iyakacin darajar aiki",
    "Oke ego ọrụ",
  ],
  expires: ["Access expires", "Àṣẹ dópin", "Izini ya ƙare", "Ikike na-agwụ"],
  previous: ["Previous", "Tí ó ṣáájú", "Na baya", "Nke gara aga"],
  next: ["Next", "Tó kàn", "Na gaba", "Osote"],
  receiptMissing: [
    "No committed submission found. Retry safely using the same operation.",
    "A kò rí ìfiránṣẹ́ tí a tọ́jú. Tún gbìyànjú pẹ̀lú àmì ìṣe kan náà.",
    "Ba a sami aikawar da aka adana ba. Sake gwadawa da aiki ɗaya.",
    "Ahụghị nzipu echekwara. Gbalịa ọzọ site n'otu ọrụ ahụ.",
  ],
  tooLarge: [
    "The selected file exceeds the size limit.",
    "Fáìlì yìí tóbi ju ààlà lọ.",
    "Fayil ɗin ya wuce iyakar girma.",
    "Faịlụ a karịrị oke nha.",
  ],
  binding: [
    "Worker identifiers must match your record. Matching names alone do not prove ownership.",
    "Àmì òṣìṣẹ́ gbọ́dọ̀ bá àkọsílẹ̀ rẹ mu. Orúkọ tó bá mu nìkan kì í jẹ́rìí ẹni tó ni í.",
    "Alamomin ma’aikaci dole su dace da bayananka. Daidaiton suna kaɗai ba hujjar mallaka ba ne.",
    "Njirimara onye ọrụ ga-adaba na ndekọ gị. Aha dakọtara naanị anaghị egosi onye nwe ya.",
  ],
  reviewer: [
    "Reviewer decisions do not change the verified trust score.",
    "Ìpinnu olùṣàyẹ̀wò kò yí ìwọ̀n ìgbẹ́kẹ̀lé tí a jẹ́rìí padà.",
    "Hukuncin mai bita ba ya canza kimar amincewa da aka tabbatar.",
    "Mkpebi onye nyocha anaghị agbanwe akara ntụkwasị obi e nyochara.",
  ],
} as const;
type Key = keyof typeof rows;
const index = { en: 0, yo: 1, ha: 2, ig: 3 } as const;
const Context = createContext<{
  language: Language;
  setLanguage: (value: Language) => void;
}>({ language: "en", setLanguage: () => {} });
export function ReviewLanguageProvider({
  children,
  initialLanguage = "en",
}: {
  children: ReactNode;
  initialLanguage?: Language;
}) {
  const [language, setLanguage] = useState<Language>(initialLanguage);
  return (
    <Context.Provider value={{ language, setLanguage }}>
      {children}
    </Context.Provider>
  );
}
export function useReviewCopy() {
  const context = useContext(Context);
  return { ...context, t: (key: Key) => rows[key][index[context.language]] };
}
export function ReviewLanguageSelector() {
  const { language, setLanguage, t } = useReviewCopy();
  return (
    <div className="flex flex-col gap-2">
      <label>
        {t("language")}{" "}
        <select
          value={language}
          className="rounded border p-2"
          onChange={(event) => {
            const next = event.target.value as Language;
            setLanguage(next);
            document.cookie = `history_language=${next}; Path=/; SameSite=Lax; Max-Age=31536000${location.protocol === "https:" ? "; Secure" : ""}`;
          }}
        >
          {["en", "yo", "ha", "ig"].map((value) => (
            <option key={value} value={value}>
              {
                { en: "English", yo: "Yorùbá", ha: "Hausa", ig: "Igbo" }[
                  value as Language
                ]
              }
            </option>
          ))}
        </select>
      </label>
      {language !== "en" && (
        <p className="text-xs text-grey-600">{t("candidate")}</p>
      )}
    </div>
  );
}
export function stateCopy(
  state: string,
  t: ReturnType<typeof useReviewCopy>["t"],
) {
  return state in rows ? t(state as Key) : state;
}
