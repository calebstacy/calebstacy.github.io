// Rewritten 2026-08-31 after the original was lost in the canvas regeneration.
// One job: the print-view toolbar button triggers the native print dialog.
(() => {
  for (const button of document.querySelectorAll("[data-print-resume]")) {
    button.addEventListener("click", () => window.print());
  }
})();
