/* One public route registry for the portfolio app and the static build.
 *
 * The browser reads this through `window.PORTFOLIO_ROUTES`; tools/build-static.js requires the
 * same file to generate independently crawlable HTML documents. Keep route identity, metadata,
 * canonical paths, and the approved fallback evidence together here so a shared link cannot drift
 * away from the React document it opens.
 */
(function publishPortfolioRoutes(root, factory) {
  const manifest = factory();
  if (typeof module !== "undefined" && module.exports) module.exports = manifest;
  if (root) root.PORTFOLIO_ROUTES = manifest;
})(typeof window !== "undefined" ? window : globalThis, function createPortfolioRoutes() {
  const siteUrl = "https://calebstacy.com";
  const socialImage = siteUrl + "/assets/portfolio-social-card.png";
  const routes = [
    {
      id: "about",
      path: "/about/",
      legacyHash: "about",
      navLabel: "About",
      heading: "Hi, I'm Caleb. I make decisions teams can reuse.",
      title: "About Caleb Stacy | Senior content designer",
      description: "Senior content designer leading complex product work from early strategy through launch, then turning strong decisions into reusable language systems.",
      fallback: {
        value: "I'm a senior content designer. My work spans product strategy and interaction language. I design onboarding, run experiments, and build systems that make good decisions easier to repeat.",
        contribution: "I've led that work on cross-functional teams spanning product, design, research, data and engineering.",
        evidence: "Before product, I spent five years teaching writing and earned an MFA in poetry. I still care about the sentence. Sometimes the work also needs a workshop, an experiment or code.",
      },
      generateDocument: true,
    },
    {
      id: "vr-education",
      path: "/work/vr-nux/",
      legacyHash: "vr-education",
      navLabel: "First-time VR",
      selectedWork: true,
      projectNumber: "01",
      heading: "First-time VR",
      title: "First-time VR | Caleb Stacy",
      description: "How I replaced a front-loaded Meta Horizon VR onboarding syllabus with behavior-triggered education, improving completion, weekly use, and retention.",
      fallback: {
        value: "People came to meet other people, but the first-run experience made them complete more than fourteen lessons before they reached the social experience. The first run took roughly 15 minutes, and roughly 70% of people dropped out.",
        contribution: "I led the education strategy and interaction language inside a broader product, design, research, data, and engineering effort. My contribution was the shift from a front-loaded syllabus to behavior-triggered education at the moment of need.",
        evidence: "Onboarding completion improved by nearly 30%, weekly active use improved by about 20%, and new-user retention improved by roughly 7%. These were project outcomes, not copy-only attribution.",
      },
      generateDocument: true,
    },
    {
      id: "portals",
      path: "/work/horizon-portals/",
      legacyHash: "portals",
      navLabel: "Horizon Portals",
      selectedWork: true,
      projectNumber: "02",
      heading: "Horizon Portals",
      title: "Horizon Portals | Caleb Stacy",
      description: "How I moved a Meta Horizon portal decision before the threshold with a proximity-based information architecture, introduced at Meta Connect 2024.",
      fallback: {
        value: "A portal gave people almost no information until after they crossed into another world. I turned physical approach into an information architecture so someone could reach a confident yes or no before stepping through.",
        contribution: "A different discipline owned the portal's physical scale and pointing behavior. I owned what appeared, when it appeared, and what each distance needed to support an informed decision.",
        evidence: "The model shipped in Meta Horizon, was introduced at Meta Connect 2024, and set a metadata precedent for other travel surfaces. Engagement and retention improved, although the figures are not public.",
      },
      generateDocument: true,
    },
    {
      id: "verso",
      path: "/work/verso/",
      legacyHash: "verso",
      navLabel: "Verso",
      selectedWork: true,
      projectNumber: "03",
      heading: "Verso",
      title: "Verso | Caleb Stacy",
      description: "How I built a content-design agent that found product context, separated evidence from judgment, and checked its own recommendations.",
      fallback: {
        value: "A longer prompt was not governance. I separated what a model could draft, what deterministic checks could evaluate, and what people still had to decide.",
        contribution: "I built the agent, an engine that computed eleven observable language dimensions, and an index that turned adopted guidance into scoped, versioned records.",
        evidence: "Over six months, Verso fingerprinted five product surfaces, logged more than 500 conversations, and spread to nearly 60 content designers before central content design assumed ownership. These figures are owner-reported internal history.",
      },
      generateDocument: true,
    },
    {
      id: "verso/agent",
      path: "/work/verso/agent/",
      legacyHash: "verso/agent",
      parentId: "verso",
      navLabel: "Agent",
      heading: "Agent",
      title: "Agent | Verso by Caleb Stacy",
      description: "What happened between a writing brief and the draft Verso returned: generate the text, measure that exact string, then check any revision.",
      fallback: {
        value: "A designer gave the internal agent a brief or a draft. Verso proposed copy, sent that proposed string to the measurement service, and used the findings to decide whether another pass was needed.",
        contribution: "The model handled the open-ended act of writing. The Engine handled the repeatable measurement.",
        evidence: "Generation can vary. The check runs as its own operation, with the context and current draft made explicit each time.",
      },
      generateDocument: true,
    },
    {
      id: "verso/engine",
      path: "/work/verso/engine/",
      legacyHash: "verso/engine",
      parentId: "verso",
      navLabel: "Engine",
      heading: "Engine",
      title: "Engine | Verso by Caleb Stacy",
      description: "What the Engine could establish about an exact string, which method supported the finding, and where the claim had to stop.",
      fallback: {
        value: "The Engine was a Python measurement service running warm on Meta's infrastructure. It did not write.",
        contribution: "Verso sent it the current string and the product context. The service computed eleven dimensions of language and returned the findings to the agent.",
        evidence: "A published framework can justify a definition or calculation. It does not validate my implementation, establish a product target, or prove how a reader will respond.",
      },
      generateDocument: true,
    },
    {
      id: "verso/index",
      path: "/work/verso/index/",
      legacyHash: "verso/index",
      parentId: "verso",
      navLabel: "Index",
      heading: "Index",
      title: "Index | Verso by Caleb Stacy",
      description: "How scattered content guidance and shipped-language evidence became records an agent could use without inventing the policy.",
      fallback: {
        value: "Content Index is my name for the matrix behind the system.",
        contribution: "I consolidated content guidance that lived across documents, chats, spreadsheets, and posts, then paired it with patterns computed from real product strings.",
        evidence: "People with authority make policy. Once an authorized rule exists, a deterministic check applies it inside the declared scope.",
      },
      generateDocument: true,
    },
    {
      id: "resume",
      path: "/resume.html",
      legacyHash: "resume",
      navLabel: "Résumé",
      heading: "Caleb Stacy",
      title: "Caleb Stacy | Senior content designer résumé",
      description: "Caleb Stacy's résumé: senior content design across product strategy, interaction language, onboarding, experimentation, and language systems.",
      generateDocument: false,
    },
    {
      id: "microcopy",
      path: "/#work-examples",
      legacyHash: "microcopy",
      hashAliases: ["work-examples"],
      navLabel: "Work examples",
      heading: "Work examples",
      title: "Work examples | Caleb Stacy",
      description: "Shipped interface writing across safety, onboarding, social connection, notifications, rewards, and spatial navigation.",
      generateDocument: false,
    },
  ];

  const selectedProjectRoutes = routes.filter((route) => route.selectedWork);
  const selectedProjectIds = selectedProjectRoutes.map((route) => route.id);
  const byId = Object.fromEntries(routes.map((route) => [route.id, route]));
  const byPath = Object.fromEntries(routes
    .filter((route) => route.path && !route.path.includes("#"))
    .map((route) => [route.path, route]));
  const byLegacyHash = Object.fromEntries(routes.flatMap((route) => (
    [route.legacyHash, ...(route.hashAliases || [])]
      .filter(Boolean)
      .map((hash) => [hash, route])
  )));

  function normalizePath(pathname) {
    if (!pathname) return "/";
    if (pathname === "/resume.html") return pathname;
    return pathname.endsWith("/") ? pathname : pathname + "/";
  }

  function fromLocation(pathname, hash) {
    const legacy = String(hash || "").replace(/^#/, "");
    if (byLegacyHash[legacy]) return byLegacyHash[legacy];
    return byPath[normalizePath(pathname)] || null;
  }

  return {
    siteUrl,
    socialImage,
    routes,
    byId,
    selectedProjectRoutes,
    selectedProjectIds,
    nextProjectId(id) {
      const index = selectedProjectIds.indexOf(id);
      return index === -1 ? null : selectedProjectIds[(index + 1) % selectedProjectIds.length];
    },
    fromLocation,
    hrefFor(id) {
      return byId[id] ? byId[id].path : "/";
    },
    canonicalFor(id) {
      return byId[id] ? siteUrl + byId[id].path : siteUrl + "/";
    },
  };
});
