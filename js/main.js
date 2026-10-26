// Loads each Vega-Lite spec from /specs and embeds it into its placeholder <div>.
// Set PLACEHOLDER_DATA to false once every chart uses real data (this hides the draft banner and tags).

const PLACEHOLDER_DATA = false;

const FIGURES = [
  "fig01-fishing-intensity-map",
  "fig02-small-multiple-maps",
  "fig03-area-fished-dumbbell",
  "fig13-fishing-persistence-hexbin",
  "fig04-production-value",
  "fig05-catch-pareto",
  "fig06-catch-value-connected-scatter",
  "fig07-production-by-state-map",
  "fig08-fishery-value-per-tonne",
  "fig09-stock-status-waffle",
  "fig10-stock-status-stream",
  "fig11-stock-status-slope",
  "fig12-healthy-heatmap",
];

async function getJSON(path, key) {
  // The single-file preview build supplies everything through window.__BUNDLE__.
  if (window.__BUNDLE__) return window.__BUNDLE__[key];
  const response = await fetch(path);
  if (!response.ok) throw new Error(`${path}: HTTP ${response.status}`);
  return response.json();
}

async function render() {
  if (PLACEHOLDER_DATA) {
    document.body.classList.add("placeholder");
    document.getElementById("draft-banner").hidden = false;
  }

  const theme = await getJSON("specs/theme.json", "theme");

  await Promise.all(
    FIGURES.map(async (id) => {
      const target = document.getElementById(`vis-${id}`);
      try {
        const spec = await getJSON(`specs/${id}.vl.json`, id);
        await vegaEmbed(target, spec, {
          config: theme,
          renderer: "svg",
          actions: { export: true, source: true, compiled: false, editor: false },
        });
        // Scale the finished chart down to fit its card, keeping its proportions.
        const svg = target.querySelector("svg");
        if (svg && svg.getAttribute("width")) {
          const w = parseFloat(svg.getAttribute("width")), h = parseFloat(svg.getAttribute("height"));
          svg.setAttribute("viewBox", `0 0 ${w} ${h}`);
          svg.removeAttribute("width");
          svg.removeAttribute("height");
          svg.style.width = "100%";
          svg.style.height = "auto";
          svg.style.maxWidth = `${w}px`;
        }
      } catch (err) {
        console.error(id, err);
        target.innerHTML =
          `<p style="color:#a63a32;font-size:14px">Could not draw ${id}: ${err.message}</p>`;
      }
    })
  );
}

// Wait for the web fonts so Vega measures text with the right typeface.
(document.fonts ? document.fonts.ready : Promise.resolve()).then(render);
