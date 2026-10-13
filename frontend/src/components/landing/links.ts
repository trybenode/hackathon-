/** Where the landing page's calls to action lead. */
export const LINKS = {
  workerSignUp: "/join",
  liveDemo: "/demo",
  developerSignUp: "/developers",
  technicalDocs: "/developer/docs",
} as const;

export const CONTACT = {
  email: "trybenode@gmail.com",
  phone: "+234 814 711 3344",
  /** Shown as plain text until there is an account to link to. */
  instagram: null as string | null,
};

/** In-page sections, shared by the header and the footer's quick links. */
export const SECTIONS = [
  { id: "how-it-works", label: "How it works" },
  { id: "features", label: "Features" },
  { id: "who-its-for", label: "Who it's for" },
] as const;
