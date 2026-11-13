/**
 * PosterMaker · Aplicación Frontend Principal (ES Module)
 */

import { els } from "./js/dom.js";
import { state } from "./js/state.js";
import { readOptions, computeGrid } from "./js/grid.js";
import { drawPreview } from "./js/preview.js";
import { clearResult, updateAll, generate } from "./js/ui.js";
import { loadFiles, resetPoster } from "./js/batch.js";
import { initInactivity } from "./js/inactivity.js";
import { initUpdater } from "./js/updater.js";

/* ---------- Eventos de Zona de Subida y Arrastre ---------- */

els.dropzone.addEventListener("click", (event) => {
  if (event.target === els.fileInput || event.target === els.fileAddInput) return;
  els.fileInput.click();
});

els.dropzone.addEventListener("keydown", (event) => {
  if (event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    els.fileInput.click();
  }
});

if (els.fileInput) {
  els.fileInput.addEventListener("click", (e) => e.stopPropagation());
  els.fileInput.addEventListener("change", () => {
    const files = els.fileInput.files;
    if (files && files.length) loadFiles(files, false);
    els.fileInput.value = "";
  });
}

if (els.fileAddInput) {
  els.fileAddInput.addEventListener("click", (e) => e.stopPropagation());
  els.fileAddInput.addEventListener("change", () => {
    const files = els.fileAddInput.files;
    if (files && files.length) loadFiles(files, true);
    els.fileAddInput.value = "";
  });
}

if (els.changeImage) {
  els.changeImage.addEventListener("click", (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (els.fileInput) els.fileInput.click();
  });
}

if (els.canvasWrap) {
  for (const eventName of ["dragenter", "dragover"]) {
    els.canvasWrap.addEventListener(eventName, (event) => {
      event.preventDefault();
      els.canvasWrap.classList.add("is-dragging");
    });
  }

  for (const eventName of ["dragleave", "dragend"]) {
    els.canvasWrap.addEventListener(eventName, (event) => {
      event.preventDefault();
      els.canvasWrap.classList.remove("is-dragging");
    });
  }

  els.canvasWrap.addEventListener("drop", (event) => {
    event.preventDefault();
    els.canvasWrap.classList.remove("is-dragging");
    const files = event.dataTransfer && event.dataTransfer.files;
    if (files && files.length) loadFiles(files, true);
  });
}

for (const eventName of ["dragenter", "dragover"]) {
  els.dropzone.addEventListener(eventName, (event) => {
    event.preventDefault();
    els.dropzone.classList.add("is-dragging");
  });
}

for (const eventName of ["dragleave", "dragend"]) {
  els.dropzone.addEventListener(eventName, (event) => {
    event.preventDefault();
    els.dropzone.classList.remove("is-dragging");
  });
}

els.dropzone.addEventListener("drop", (event) => {
  event.preventDefault();
  els.dropzone.classList.remove("is-dragging");
  const files = event.dataTransfer && event.dataTransfer.files;
  if (files && files.length) loadFiles(files);
});

els.form.addEventListener("submit", (event) => {
  event.preventDefault();
  generate();
});

/* ---------- Sincronización de Opciones ---------- */

function onOptionsChanged() {
  clearResult();
  updateAll();
}

for (const element of [
  els.pagesWide,
  els.paper,
  els.margin,
  els.overlap,
  els.dpi,
  els.marks,
  els.labels,
  els.guide,
  els.skipGuide,
  els.separatePosters,
]) {
  if (element) {
    element.addEventListener("input", onOptionsChanged);
    element.addEventListener("change", onOptionsChanged);
  }
}

for (const radio of document.querySelectorAll(
  'input[name="orientation"], input[name="dimension_mode"], input[name="color_mode"]'
)) {
  radio.addEventListener("change", onOptionsChanged);
}

/* ---------- Interacción con el Lienzo Canvas ---------- */

els.canvas.addEventListener("mousemove", (event) => {
  if (!state.currentGrid || !state.previewDimensions) return;
  const rect = els.canvas.getBoundingClientRect();
  const mouseX = event.clientX - rect.left;
  const mouseY = event.clientY - rect.top;

  const { width, height } = state.previewDimensions;
  const grid = state.currentGrid;

  const colWidth = (width * grid.usableWidth) / grid.posterWidth;
  const rowHeight = (height * grid.usableHeight) / grid.posterHeight;

  let col = Math.floor(mouseX / colWidth);
  let row = Math.floor(mouseY / rowHeight);

  col = Math.max(0, Math.min(grid.pagesWide - 1, col));
  row = Math.max(0, Math.min(grid.pagesHigh - 1, row));
  const pageIndex = row * grid.pagesWide + col + 1;

  if (
    !state.hoveredTile ||
    state.hoveredTile.row !== row ||
    state.hoveredTile.col !== col
  ) {
    state.hoveredTile = { row, col, index: pageIndex };
    if (els.hoverTileInfo) {
      els.hoverTileInfo.hidden = false;
      els.hoverTileInfo.textContent = `Hoja ${pageIndex} de ${grid.totalPages} · Fila ${row + 1}, Col. ${col + 1}`;
    }
    requestAnimationFrame(() => drawPreview(grid));
  }
});

els.canvas.addEventListener("mouseleave", () => {
  if (state.hoveredTile) {
    state.hoveredTile = null;
    if (els.hoverTileInfo) {
      els.hoverTileInfo.hidden = true;
      els.hoverTileInfo.textContent = "";
    }
    if (state.currentGrid) {
      requestAnimationFrame(() => drawPreview(state.currentGrid));
    }
  }
});

els.newPoster.addEventListener("click", resetPoster);

const resizeObserver = new ResizeObserver(() => {
  if (state.image) {
    const grid = computeGrid(readOptions());
    requestAnimationFrame(() => drawPreview(grid));
  }
});
resizeObserver.observe(els.canvasWrap);

window.addEventListener("resize", () => {
  if (state.image) {
    const grid = computeGrid(readOptions());
    requestAnimationFrame(() => drawPreview(grid));
  }
});

/* ---------- Inicialización ---------- */

initInactivity();
initUpdater();
updateAll();
