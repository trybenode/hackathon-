/** Where the landing page's calls to action lead. */
export const LINKS = {
  workerSignUp: "/join",
  developerSignUp: "/developers",
  technicalDocs: "/developer/docs",
} as const;

/** In-page sections, shared by the header and the footer's quick links. */
export const SECTIONS = [
  { id: "how-it-works", label: "How it works" },
  { id: "features", label: "Features" },
  { id: "who-its-for", label: "Who it's for" },
] as const;
