import { PAPERS, MM_PER_INCH } from "./constants.js";
import { els } from "./dom.js";
import { state } from "./state.js";

export function readOptions() {
  const dimMode = document.querySelector('input[name="dimension_mode"]:checked')?.value || "wide";
  const dimCount = Number(els.pagesWide.value);
  const colorMode = document.querySelector('input[name="color_mode"]:checked')?.value || "color";
  const guideChecked = Boolean(
    els.guide ? els.guide.checked : (els.skipGuide ? !els.skipGuide.checked : false)
  );

  return {
    dimMode,
    dimCount,
    pagesWide: dimMode === "wide" ? dimCount : null,
    pagesHigh: dimMode === "high" ? dimCount : null,
    orientation: document.querySelector('input[name="orientation"]:checked').value,
    paper: els.paper.value,
    color: colorMode,
    margin: Number(els.margin.value),
    overlap: Number(els.overlap.value),
    dpi: Number(els.dpi.value),
    marks: Boolean(els.marks && els.marks.checked),
    labels: Boolean(els.labels && els.labels.checked),
    guide: guideChecked,
    skipGuide: !guideChecked,
    separatePosters: Boolean(els.separatePosters && els.separatePosters.checked),
  };
}

export function computeGrid(options) {
  const paper = PAPERS[options.paper] || PAPERS.letter;
  let pageWidth = paper.width;
  let pageHeight = paper.height;
  if (options.orientation === "landscape") {
    [pageWidth, pageHeight] = [pageHeight, pageWidth];
  }

  const usableWidth = pageWidth - options.margin * 2;
  const usableHeight = pageHeight - options.margin * 2;

  let pagesWide = options.dimMode === "wide" ? options.dimCount : 1;
  let pagesHigh = options.dimMode === "high" ? options.dimCount : 1;
  let posterWidth = pagesWide * usableWidth;
  let posterHeight = pagesHigh * usableHeight;
  let effectiveDpi = null;

  if (state.image) {
    const iw = state.image.naturalWidth;
    const ih = state.image.naturalHeight;
    const aspect = iw / ih;

    if (options.dimMode === "wide") {
      pagesWide = options.dimCount;
      posterWidth = pagesWide * usableWidth;
      posterHeight = posterWidth / aspect;
      pagesHigh = Math.max(1, Math.ceil(posterHeight / usableHeight - 1e-9));
    } else {
      pagesHigh = options.dimCount;
      posterHeight = pagesHigh * usableHeight;
      posterWidth = posterHeight * aspect;
      pagesWide = Math.max(1, Math.ceil(posterWidth / usableWidth - 1e-9));
    }

    effectiveDpi = Math.min(
      iw / (posterWidth / MM_PER_INCH),
      ih / (posterHeight / MM_PER_INCH)
    );
  }

  return {
    pageWidth,
    pageHeight,
    usableWidth,
    usableHeight,
    posterWidth,
    posterHeight,
    pagesWide,
    pagesHigh,
    totalPages: pagesWide * pagesHigh,
    effectiveDpi,
  };
}
