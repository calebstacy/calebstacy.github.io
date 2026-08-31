// Project facts and résumé records. Case-study prose is authored from intake, not lifted.
window.PORTFOLIO = {
  identity: {
    name: "Caleb Stacy",
    title: "Senior content designer",
    differentiator: "Product strategy · interaction language",
    thesis: "I lead complex product work from early strategy through launch, then turn the decisions worth repeating into systems people and agents can use.",
    location: "Richmond, Virginia · Local + remote",
    site: "calebstacy.com",
  },
  /* Record storage is intentionally unordered. route-manifest.js owns selected-work order,
     numbering, and the loop; `projects` is derived from that registry after this object closes. */
  projectRecords: [
    {
      id: "verso", title: "Verso",
      context: "AI content governance · Meta · 2025 to 2026",
      subPages: [
        { id: "verso/agent", label: "Agent" },
        { id: "verso/engine", label: "Engine" },
        { id: "verso/index", label: "Index" },
      ],
      statement: "Making language decisions inspectable",
      summary: "Content designers used Verso to write, review, research, compare, and specify product language. It found the relevant context, ran the applicable checks, made a content-design judgment, and checked its own recommendation.",
      outcomeLabel: "At handoff",
      results: ["Five product surfaces fingerprinted from shipped strings", "More than 500 agent conversations", "Used by nearly 60 content designers"],
      role: "Sole creator · content strategy, interaction design, measurement, and implementation",
      team: "Solo build · central content design adopted the system and owns it now",
      timeline: "2025 to 2026",
      surface: "Internal content-design tooling at Meta",
      teamSurface: "Solo, on Meta's internal infrastructure. I partnered with central content design to adopt it, and they own it now.",
      artifacts: [
        { src: "/assets/work/verso-evidence-cabinet.png", alt: "Clay render of a card-index cabinet holding filed evidence", label: "The index, as an object", caption: "A rendered stand-in for the index: each surface gets its own drawer, and each measurable dimension its own card. No internal Meta material, index values, or product strings are shown." },
      ],
      sources: ["Central brand guidance", "Product-area guidance", "Docs, chats, and spreadsheets", "Real shipped strings"],
      ledger: [{ value: "11", label: "Measured dimensions" }, { value: "5", label: "Surfaces fingerprinted" }, { value: "6 mo", label: "Solo build" }, { value: "500+", label: "Agent conversations" }],
      pipeline: ["Ingest the real shipped strings of a product surface.", "Fingerprint the corpus across eleven measurable dimensions.", "Serve it warm, so measurement is cheap enough to call on every draft.", "The agent measures its own draft and adjusts until it lands inside the deviation."],
      quote: "“Be concise” names something the reader feels. It does not name anything the writer did.",
      quoteBy: "The receiver-side problem",
    },
    {
      id: "vr-education", title: "First-time VR",
      context: "New-user education · Meta Horizon · 2025",
      statement: "Replacing the onboarding syllabus with education at the moment of need",
      summary: "Meta Horizon's first-run experience taught people how to use VR before letting them experience why they might want to. I led the education strategy and interaction language for a new model: let people reach the social experience, then teach each action when their behavior makes the need clear.",
      outcomeLabel: "Results",
      results: ["Onboarding completion improved by nearly 30%", "Weekly active use improved by about 20%", "New-user retention improved by roughly 7%"],
      role: "Content designer · education strategy and interaction language",
      team: "Product · Design · Research and data · 3 engineers · 5 partner teams",
      timeline: "2025",
      surface: "Meta Horizon Worlds, first-run VR",
      teamSurface: "Product · Design · 3 engineers · 5 partner teams · Meta Horizon Worlds, first-run VR",
      artifacts: [],
      evidenceNote: "The measured lifts are on the cover and the education strategy is stated in full above. The first-run sequence itself stays unpublished because the captures belong to Meta. A rebuilt approximation of an onboarding flow would be the one thing this document refuses to do: present a reconstruction as the experiment.",
      sources: ["World selection", "Recording consent", "Fourteen-plus lessons", "Starter world loading"],
      ledger: [{ value: "72%", label: "Original drop-off" }, { value: "15 min", label: "Original onboarding" }, { value: "90 s", label: "Of loading" }, { value: "14+", label: "Lessons before play" }],
      pipeline: ["Teach one action on the input that needs it.", "Reinforce in context when state changes.", "Nudge on the controller, not in a modal.", "Never replay the syllabus."],
      quote: "Stop teaching everything once. Teach one action, in the moment it matters.",
      quoteBy: "Education strategy principle",
    },
    {
      id: "portals", title: "Horizon Portals",
      context: "Spatial interaction · Meta Horizon · 2024",
      statement: "Making the decision before the threshold",
      summary: "A portal once gave people almost no information until after they crossed into another world. I turned physical approach into an information architecture, so someone could reach a confident yes or no before stepping through.",
      outcomeLabel: "What changed",
      outcomeProse: "Shipped in Meta Horizon and featured in the Meta Connect 2024 keynote. Engagement and retention improved; the figures are not public.",
      role: "Content design lead",
      team: "Product, Engineering, UXR, and Design",
      timeline: "2024",
      surface: "Spatial navigation in Meta Horizon",
      teamSurface: "Product, Engineering, UXR, and Design · spatial navigation in Meta Horizon",
      heroVideo: "/assets/work/portals-connect-hero.mp4",
      heroPoster: "/assets/work/portals-connect-poster.jpg",
      heroCaption: "Meta Connect 2024. Mark Zuckerberg introduces the portal experience on stage.",
      artifacts: [
        { src: "/assets/work/card-portals.jpg", alt: "A portal card showing a world, who is inside, and one action", label: "Shipped surface", caption: "A portal at approach distance: identity, who is already inside, and the one available action." },
      ],
      sources: ["Identity at a distance", "Social context", "Available action", "Full decision context"],
      ledger: [{ value: "3", label: "Disclosure distances" }, { value: "A/B", label: "Tested with UXR" }, { value: "Connect 2024", label: "Public reveal" }, { value: "Shipped", label: "In Horizon" }],
      pipeline: ["At distance, show identity only.", "On interest, add the available action.", "On approach, reveal the full decision context.", "Never show maximum entries at once."],
      quote: "State of intent, not maximum entries.",
      quoteBy: "Spatial IA principle",
    },
  ],
  chapters: [
    { id: "situation", label: "Situation" }, { id: "task", label: "Task" },
    { id: "action", label: "Action" }, { id: "result", label: "Result" },
  ],
  contact: "https://www.linkedin.com/in/caleb-stacyrva/",
  resumeSummary: "Senior content designer with 11 years across product and education. I lead work upstream of interface copy, from product strategy and language models through research, experiments, and launch. I also build measurable voice standards, terminology schemas, and checks that help writers and AI agents make reliable decisions.",
  experience: [
    {
      when: "Nov 2022 - May 2026", org: "Meta", role: "Content designer → Senior content designer · Horizon, experimentation, and AI",
      bullets: [
        "Created Meta's content-standards infrastructure. Built Verso, the first content-design agent at Meta to enforce standards deterministically, plus a lint toolkit, an 11-dimension measurement engine with voice baselines derived from shipped strings across five product surfaces, and a structured index of terminology rules and review blockers.",
        "Led travel terminology across Meta Horizon OS: one vocabulary for calling, sessions, and travel across VR, mobile, and desktop. Also led the naming audit for the Meta Quest-to-Horizon OS rebrand.",
        "Established Meta Horizon's first content experimentation practice and led content designers across its major product areas, representing the organization. Built workshops and working tools for writing hypotheses and tracking tests.",
        "Brought content designers into agentic workflows through workshops and office hours. Taught local agent setup, then helped designers author reusable skill files and deterministic scripts for rules prose guidance could not reliably enforce.",
        "Helped turn the Meta Horizon phone app from a headset utility into a repeat-use mobile product. Led content from the early journeys and an executive strategy one-pager through launch experiments. A feed test lifted 28-day retention by about 15%; a quests homepage increased daily active use by nearly 5% in its first test.",
        "Defined the strategy, jobs to be done, metadata, and progressive-disclosure framework for Horizon Portals. The work earned VP alignment, shipped in Meta Horizon, and appeared in the Meta Connect 2024 keynote.",
        "Replaced a 14-plus-lesson VR onboarding syllabus with just-in-time spatial education. Onboarding completion improved by nearly 30%, weekly active use by about 20%, and new-user retention by roughly 7%. The strategy and components were adopted by the Meta Quest onboarding team.",
      ],
    },
    {
      when: "Oct 2021 - Oct 2022", org: "Digbi Health", role: "Lead UX writer",
      bullets: [
        "Led end-to-end product content for a precision-health startup, translating microbiome, genetic, and clinical data into personalized journeys from onboarding through behavior change.",
      ],
    },
    {
      when: "Apr 2020 - Oct 2021", org: "8x8", role: "UX writer",
      bullets: [
        "Made enterprise voice, video, chat, contact-center, and phone-administration tools understandable to the business owners who had to configure them.",
      ],
    },
    {
      when: "Jul 2015 - Jun 2020", org: "WVU, VCU, and Army Logistics University", role: "Professor",
      bullets: [
        "Spent five years teaching composition and poetry at WVU and VCU, then training Army officers to turn complex, high-stakes information into clear, direct language.",
      ],
    },
  ],
  education: [
    { org: "Virginia Commonwealth University", role: "MFA, Poetry", when: "2018" },
    { org: "West Virginia University", role: "BA, English", when: "2014" },
  ],
  tools: ["Product strategy", "Interaction language", "Onboarding and education", "Experiment design", "Content modeling", "Terminology and taxonomy", "AI workflows and evals", "Workshop facilitation", "Figma", "Python"],
  publicWork: [
    {
      title: "Working papers",
      body: "A running list of short public studies on measuring and governing product language. calebstacy.com/papers",
    },
    {
      title: "slop-no-more",
      body: "A deterministic scanner for the rhetorical moves that make prose read as machine-written: a 26-family catalog, severity tiers and repair rules.",
    },
  ],
};

window.PORTFOLIO.projects = window.PORTFOLIO_ROUTES.selectedProjectRoutes.map((route) => {
  const project = window.PORTFOLIO.projectRecords.find((record) => record.id === route.id);
  if (!project) throw new Error("Missing project record for selected route: " + route.id);
  return { ...project, number: route.projectNumber };
});
delete window.PORTFOLIO.projectRecords;
