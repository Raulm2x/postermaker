"use strict";

const PAPERS = {
  letter: { name: "Carta", width: 215.9, height: 279.4 },
  carta: { name: "Carta", width: 215.9, height: 279.4 },
  a4: { name: "A4", width: 210, height: 297 },
  a3: { name: "A3", width: 297, height: 420 },
  a5: { name: "A5", width: 148, height: 210 },
  legal: { name: "Oficio", width: 215.9, height: 355.6 },
  oficio: { name: "Oficio", width: 215.9, height: 355.6 },
  tabloid: { name: "Tabloide", width: 279.4, height: 431.8 },
  tabloide: { name: "Tabloide", width: 279.4, height: 431.8 },
};

const MAX_UPLOAD_BYTES = 25 * 1024 * 1024;
const MAX_TOTAL_PAGES = 150;
const MM_PER_INCH = 25.4;

const els = {
  dropzone: document.getElementById("dropzone"),
  fileInput: document.getElementById("file-input"),
  changeImage: document.getElementById("change-image"),
  previewStage: document.getElementById("preview-stage"),
  canvas: document.getElementById("preview-canvas"),
  canvasWrap: document.getElementById("canvas-wrap"),
  imageMeta: document.getElementById("image-meta"),
  hoverTileInfo: document.getElementById("hover-tile-info"),
  form: document.getElementById("options-form"),
  pagesWide: document.getElementById("pages-wide"),
  pagesWideOut: document.getElementById("pages-wide-out"),
  dimHint: document.getElementById("dim-hint"),
  paper: document.getElementById("paper"),
  margin: document.getElementById("margin"),
  marginOut: document.getElementById("margin-out"),
  overlap: document.getElementById("overlap"),
  overlapOut: document.getElementById("overlap-out"),
  dpi: document.getElementById("dpi"),
  marks: document.getElementById("marks"),
  labels: document.getElementById("labels"),
  guide: document.getElementById("guide"),
  dimensions: document.getElementById("dimensions"),
  summaryDetail: document.getElementById("summary-detail"),
  dpiBadge: document.getElementById("dpi-badge"),
  resolutionNote: document.getElementById("resolution-note"),
  generate: document.getElementById("generate"),
  status: document.getElementById("status"),
  resultCard: document.getElementById("result-card"),
  resultDetail: document.getElementById("result-detail"),
  downloadLink: document.getElementById("download-link"),
  downloadZipLink: document.getElementById("download-zip-link"),
  resultPreview: document.getElementById("result-preview"),
  newPoster: document.getElementById("new-poster"),
  calibrationLink: document.getElementById("calibration-link"),
};

const state = {
  file: null,
  image: null,
  imageUrl: null,
  generating: false,
  invalid: false,
  hoveredTile: null,
  currentGrid: null,
};

const decimal = new Intl.NumberFormat("es-ES", {
  maximumFractionDigits: 1,
  minimumFractionDigits: 0,
});

function readOptions() {
  const dimMode = document.querySelector('input[name="dimension_mode"]:checked')?.value || "wide";
  const dimCount = Number(els.pagesWide.value);
  const colorMode = document.querySelector('input[name="color_mode"]:checked')?.value || "color";

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
    marks: els.marks.checked,
    labels: els.labels.checked,
    guide: Boolean(els.guide && els.guide.checked),
  };
}

function computeGrid(options) {
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

function setStatus(message, type = "") {
  els.status.textContent = message;
  els.status.className = `status ${type}`.trim();
  els.status.hidden = !message;
}

function clearResult() {
  els.resultCard.hidden = true;
  els.downloadLink.href = "#";
  if (els.downloadZipLink) els.downloadZipLink.href = "#";
  els.resultPreview.href = "#";
}

function updateCalibrationLink(paper) {
  const info = PAPERS[paper] || PAPERS.letter;
  els.calibrationLink.href = `/api/calibration?paper=${encodeURIComponent(paper)}`;
  els.calibrationLink.textContent = `Descargar calibración ${info.name}`;
}

function updateLabels(options) {
  if (options.dimMode === "wide") {
    els.pagesWideOut.textContent = `${options.dimCount} hoja${options.dimCount === 1 ? "" : "s"} de ancho`;
    if (els.dimHint) {
      els.dimHint.textContent = "El alto se calcula automáticamente para conservar la proporción.";
    }
  } else {
    els.pagesWideOut.textContent = `${options.dimCount} hoja${options.dimCount === 1 ? "" : "s"} de alto`;
    if (els.dimHint) {
      els.dimHint.textContent = "El ancho se calcula automáticamente para conservar la proporción.";
    }
  }
  els.marginOut.textContent = `${options.margin} mm`;
  els.overlapOut.textContent = `${options.overlap} mm`;
}

function updateSummary(options, grid) {
  updateLabels(options);
  updateCalibrationLink(options.paper);

  const hasImage = Boolean(state.image);
  els.generate.disabled = !hasImage || state.invalid || state.generating;

  if (!hasImage) {
    els.dimensions.textContent = "—";
    els.summaryDetail.textContent = "Elige una imagen para empezar.";
    els.dpiBadge.hidden = true;
    els.resolutionNote.hidden = true;
    return;
  }

  const tooManyPages = grid.totalPages > MAX_TOTAL_PAGES;
  state.invalid = tooManyPages || grid.usableWidth <= 0 || grid.usableHeight <= 0;

  els.dimensions.textContent =
    `${decimal.format(grid.posterWidth / 10)} × ` +
    `${decimal.format(grid.posterHeight / 10)} cm`;

  const orientationText =
    options.orientation === "portrait" ? "vertical" : "horizontal";
  const lastRowHeight =
    grid.posterHeight - (grid.pagesHigh - 1) * grid.usableHeight;
  const partialRow = lastRowHeight < grid.usableHeight - 0.5;
  els.summaryDetail.textContent =
    `${grid.pagesWide} × ${grid.pagesHigh} hojas · ` +
    `${grid.totalPages} página${grid.totalPages === 1 ? "" : "s"} · ` +
    `${(PAPERS[options.paper] || PAPERS.letter).name} ${orientationText}` +
    (partialRow ? " · última fila parcial" : "");

  const dpi = grid.effectiveDpi;
  els.dpiBadge.hidden = false;
  els.dpiBadge.className = "dpi-badge";
  if (dpi >= 300) {
    els.dpiBadge.classList.add("good");
    els.dpiBadge.textContent = `${Math.round(dpi)} ppp`;
  } else if (dpi >= 150) {
    els.dpiBadge.classList.add("warn");
    els.dpiBadge.textContent = `${Math.round(dpi)} ppp`;
  } else {
    els.dpiBadge.classList.add("bad");
    els.dpiBadge.textContent = `${Math.round(dpi)} ppp`;
  }

  els.resolutionNote.classList.toggle("is-error", tooManyPages);
  if (tooManyPages) {
    els.resolutionNote.hidden = false;
    els.resolutionNote.textContent =
      `Este ajuste produciría ${grid.totalPages} hojas. ` +
      `El máximo es ${MAX_TOTAL_PAGES}: reduce el ancho o cambia de orientación.`;
  } else if (dpi < 150) {
    els.resolutionNote.hidden = false;
    els.resolutionNote.textContent =
      "La imagen tiene poca resolución para este tamaño. " +
      "Se recomiendan al menos 150 ppp para imprimir nítido.";
  } else {
    els.resolutionNote.hidden = true;
    els.resolutionNote.textContent = "";
  }

  els.generate.disabled = state.invalid || state.generating;
}

function drawPreview(grid) {
  if (!state.image) return;

  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  const wrapStyle = getComputedStyle(els.canvasWrap);
  const availableWidth =
    els.canvasWrap.clientWidth -
    parseFloat(wrapStyle.paddingLeft) -
    parseFloat(wrapStyle.paddingRight);

  if (availableWidth <= 0) return;

  const aspect = grid.posterWidth / grid.posterHeight;
  let width = availableWidth;
  let height = width / aspect;
  const maxHeight = Math.min(window.innerHeight * 0.62, 720);

  if (height > maxHeight) {
    height = maxHeight;
    width = height * aspect;
  }

  width = Math.max(120, width);
  height = Math.max(120, height);

  state.currentGrid = grid;
  state.previewDimensions = { width, height };

  els.canvas.style.width = `${width}px`;
  els.canvas.style.height = `${height}px`;
  els.canvas.width = Math.round(width * dpr);
  els.canvas.height = Math.round(height * dpr);

  const ctx = els.canvas.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, width, height);

  ctx.fillStyle = "#ffffff";
  ctx.fillRect(0, 0, width, height);

  const image = state.image;
  const iw = image.naturalWidth;
  const ih = image.naturalHeight;
  const targetAspect = aspect;
  let sourceWidth;
  let sourceHeight;

  if (iw / ih > targetAspect) {
    sourceHeight = ih;
    sourceWidth = ih * targetAspect;
  } else {
    sourceWidth = iw;
    sourceHeight = iw / targetAspect;
  }

  const sourceX = (iw - sourceWidth) / 2;
  const sourceY = (ih - sourceHeight) / 2;

  const options = readOptions();
  if (options.color === "grayscale") {
    ctx.filter = "grayscale(100%)";
  } else if (options.color === "monochrome") {
    ctx.filter = "grayscale(100%) contrast(300%)";
  } else {
    ctx.filter = "none";
  }

  ctx.imageSmoothingEnabled = true;
  ctx.imageSmoothingQuality = "high";
  ctx.drawImage(
    image,
    sourceX,
    sourceY,
    sourceWidth,
    sourceHeight,
    0,
    0,
    width,
    height
  );
  ctx.filter = "none";

  const lineWidth = Math.max(1, Math.min(2, width / 480));
  const verticals = [];
  const horizontals = [];

  for (let col = 1; col < grid.pagesWide; col += 1) {
    verticals.push((width * (col * grid.usableWidth)) / grid.posterWidth);
  }
  for (let row = 1; row < grid.pagesHigh; row += 1) {
    horizontals.push(
      (height * (row * grid.usableHeight)) / grid.posterHeight
    );
  }

  // Primero una línea clara para que se vea sobre fotos oscuras.
  ctx.strokeStyle = "rgba(255, 255, 255, 0.82)";
  ctx.lineWidth = lineWidth * 2.6;
  ctx.beginPath();
  for (const x of verticals) {
    ctx.moveTo(x, 0);
    ctx.lineTo(x, height);
  }
  for (const y of horizontals) {
    ctx.moveTo(0, y);
    ctx.lineTo(width, y);
  }
  ctx.stroke();

  ctx.strokeStyle = "#e4572e";
  ctx.lineWidth = lineWidth;
  ctx.beginPath();
  for (const x of verticals) {
    ctx.moveTo(x, 0);
    ctx.lineTo(x, height);
  }
  for (const y of horizontals) {
    ctx.moveTo(0, y);
    ctx.lineTo(width, y);
  }
  ctx.stroke();

  // Si hay una celda bajo el cursor, resaltarla suavemente
  if (state.hoveredTile) {
    const { row, col } = state.hoveredTile;
    const hx0 = (width * (col * grid.usableWidth)) / grid.posterWidth;
    const hx1 = Math.min(width, (width * ((col + 1) * grid.usableWidth)) / grid.posterWidth);
    const hy0 = (height * (row * grid.usableHeight)) / grid.posterHeight;
    const hy1 = Math.min(height, (height * ((row + 1) * grid.usableHeight)) / grid.posterHeight);

    ctx.fillStyle = "rgba(228, 87, 46, 0.22)";
    ctx.fillRect(hx0, hy0, hx1 - hx0, hy1 - hy0);
    ctx.strokeStyle = "#e4572e";
    ctx.lineWidth = Math.max(2, lineWidth * 1.8);
    ctx.strokeRect(hx0, hy0, hx1 - hx0, hy1 - hy0);
  }

  ctx.strokeStyle = "rgba(23, 33, 31, 0.22)";
  ctx.lineWidth = 1;
  ctx.strokeRect(0.5, 0.5, width - 1, height - 1);
}

function updateImageMeta() {
  if (!state.file || !state.image) {
    els.imageMeta.textContent = "—";
    return;
  }
  const name = state.file.name;
  const width = state.image.naturalWidth;
  const height = state.image.naturalHeight;
  els.imageMeta.textContent = `${name} · ${width} × ${height} px`;
}

function updateAll() {
  const options = readOptions();
  const grid = computeGrid(options);
  updateSummary(options, grid);
  updateImageMeta();

  if (state.image) {
    requestAnimationFrame(() => drawPreview(grid));
  }
}

function showImage(file, image, objectUrl) {
  if (state.imageUrl) {
    URL.revokeObjectURL(state.imageUrl);
  }
  state.file = file;
  state.image = image;
  state.imageUrl = objectUrl;
  state.invalid = false;

  els.dropzone.hidden = true;
  els.previewStage.hidden = false;
  els.changeImage.hidden = false;
  clearResult();
  setStatus("");
  updateAll();
}

function resetPoster() {
  if (state.imageUrl) {
    URL.revokeObjectURL(state.imageUrl);
  }
  state.file = null;
  state.image = null;
  state.imageUrl = null;
  state.generating = false;
  state.invalid = false;

  els.fileInput.value = "";
  els.dropzone.hidden = false;
  els.previewStage.hidden = true;
  els.changeImage.hidden = true;
  els.generate.classList.remove("loading");
  els.generate.removeAttribute("aria-busy");
  els.generate.querySelector(".button-label").textContent = "Crear PDF";
  clearResult();
  setStatus("");
  updateAll();
}

function loadFile(file) {
  if (!file) return;

  const isImage =
    ["image/jpeg", "image/png", "image/webp"].includes(file.type) ||
    /\.(jpe?g|png|webp)$/i.test(file.name);

  if (!isImage) {
    setStatus("Formato no compatible. Usa un archivo JPG, PNG o WebP.", "error");
    return;
  }
  if (file.size > MAX_UPLOAD_BYTES) {
    setStatus("La imagen supera el límite de 25 MB.", "error");
    return;
  }

  const objectUrl = URL.createObjectURL(file);
  const image = new Image();

  image.onload = () => {
    if (!image.naturalWidth || !image.naturalHeight) {
      URL.revokeObjectURL(objectUrl);
      setStatus("No se pudo leer la imagen. Prueba con otro archivo.", "error");
      return;
    }
    showImage(file, image, objectUrl);
  };

  image.onerror = () => {
    URL.revokeObjectURL(objectUrl);
    setStatus("No se pudo leer la imagen. Prueba con otro archivo.", "error");
  };

  image.src = objectUrl;
}

function formatBytes(bytes) {
  if (!Number.isFinite(bytes) || bytes <= 0) return "";
  const units = ["B", "KB", "MB", "GB"];
  let value = bytes;
  let index = 0;
  while (value >= 1024 && index < units.length - 1) {
    value /= 1024;
    index += 1;
  }
  const digits = index === 0 ? 0 : 1;
  return `${value.toFixed(digits)} ${units[index]}`;
}

function setGenerating(value) {
  state.generating = value;
  els.generate.classList.toggle("loading", value);
  els.generate.disabled = value || state.invalid || !state.image;
  els.generate.querySelector(".button-label").textContent = value
    ? "Generando PDF…"
    : "Crear PDF";
  if (value) {
    els.generate.setAttribute("aria-busy", "true");
  } else {
    els.generate.removeAttribute("aria-busy");
  }
}

function showResult(data) {
  clearResult();

  const size = formatBytes(data.sizeBytes);
  els.resultDetail.textContent =
    `${data.pagesWide} × ${data.pagesHigh} hojas · ` +
    `${decimal.format(data.widthCm)} × ${decimal.format(data.heightCm)} cm` +
    (size ? ` · ${size}` : "");

  els.downloadLink.href = data.downloadUrl;
  els.downloadLink.setAttribute("download", data.filename || "poster.pdf");
  els.downloadLink.querySelector(".download-label").textContent = size
    ? `Descargar PDF (${size})`
    : "Descargar PDF";

  if (els.downloadZipLink) {
    els.downloadZipLink.href = data.downloadZipUrl || `/api/download/${data.id}/zip`;
    const base = (data.filename || "poster.pdf").replace(/\.pdf$/i, "");
    els.downloadZipLink.setAttribute("download", `${base}_piezas.zip`);
  }

  els.resultPreview.href = data.previewUrl;
  els.resultCard.hidden = false;
  els.resultCard.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

async function generate() {
  if (!state.file || state.generating || state.invalid) return;

  const options = readOptions();
  const formData = new FormData();
  formData.append("image", state.file, state.file.name);
  formData.append("dimension_mode", options.dimMode);
  if (options.dimMode === "wide") {
    formData.append("pages_wide", String(options.dimCount));
  } else {
    formData.append("pages_high", String(options.dimCount));
  }
  formData.append("orientation", options.orientation);
  formData.append("paper", options.paper);
  formData.append("color_mode", options.color);
  formData.append("margin", String(options.margin));
  formData.append("overlap", String(options.overlap));
  formData.append("dpi", String(options.dpi));
  formData.append("marks", options.marks ? "true" : "false");
  formData.append("labels", options.labels ? "true" : "false");
  formData.append("guide", options.guide ? "true" : "false");

  setGenerating(true);
  setStatus("Generando el PDF. Las imágenes grandes pueden tardar unos segundos…");
  clearResult();

  try {
    const response = await fetch("/api/generate", {
      method: "POST",
      body: formData,
    });

    const raw = await response.text();
    let data = null;
    try {
      data = JSON.parse(raw);
    } catch {
      data = null;
    }

    if (!response.ok) {
      throw new Error(
        (data && data.error) ||
          `No se pudo generar el PDF (error ${response.status}).`
      );
    }
    if (!data || !data.downloadUrl) {
      throw new Error("El servidor devolvió una respuesta inesperada.");
    }

    setStatus("");
    showResult(data);
  } catch (error) {
    const message =
      error instanceof Error ? error.message : "No se pudo generar el PDF.";
    setStatus(message, "error");
  } finally {
    setGenerating(false);
    updateAll();
  }
}

/* ---------- Eventos ---------- */

els.dropzone.addEventListener("click", (event) => {
  if (event.target === els.fileInput) return;
  els.fileInput.click();
});
els.dropzone.addEventListener("keydown", (event) => {
  if (event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    els.fileInput.click();
  }
});

els.fileInput.addEventListener("change", () => {
  const file = els.fileInput.files && els.fileInput.files[0];
  if (file) loadFile(file);
});

els.changeImage.addEventListener("click", () => els.fileInput.click());

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
  const file = event.dataTransfer && event.dataTransfer.files[0];
  if (file) loadFile(file);
});

els.form.addEventListener("submit", (event) => {
  event.preventDefault();
  generate();
});

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

// ---------- Gestión de inactividad y recursos del servidor ----------

// Heartbeat periódico para mantener el servidor despierto mientras la app esté abierta
setInterval(() => {
  fetch("/api/heartbeat", { method: "POST" }).catch(() => {});
}, 45000);

// Notificar al servidor cuando la pestaña se cierra o se navega a otro sitio
window.addEventListener("beforeunload", () => {
  if (navigator.sendBeacon) {
    navigator.sendBeacon("/api/tab-closed");
  }
});

// Botón de apagado manual y liberación de memoria
const shutdownBtn = document.getElementById("btn-shutdown");
if (shutdownBtn) {
  shutdownBtn.addEventListener("click", async () => {
    const confirmShutdown = window.confirm(
      "¿Deseas cerrar el servidor local de PosterMaker y liberar memoria del sistema?\n\nPodrás volver a abrirlo en cualquier momento desde tu menú de aplicaciones."
    );
    if (!confirmShutdown) return;

    shutdownBtn.disabled = true;
    shutdownBtn.textContent = "Liberando recursos...";

    try {
      await fetch("/api/shutdown", { method: "POST" });
    } catch (e) {
      // Proceso terminado
    }

    document.body.innerHTML = `
      <div style="min-height: 100vh; display: flex; flex-direction: column; align-items: center; justify-content: center; font-family: system-ui, -apple-system, sans-serif; text-align: center; padding: 24px; background: #fffdf8; color: #17211f;">
        <div style="max-width: 480px; background: #ffffff; border: 1px solid rgba(23,33,31,0.12); border-radius: 14px; padding: 36px 28px; box-shadow: 0 10px 30px rgba(0,0,0,0.06);">
          <div style="font-size: 2.2rem; margin-bottom: 12px;">✅</div>
          <h1 style="font-size: 1.35rem; font-weight: 700; margin-bottom: 10px; color: #17211f;">Recursos del sistema liberados</h1>
          <p style="font-size: 0.95rem; color: #526360; line-height: 1.55; margin-bottom: 22px;">
            El servidor de PosterMaker se ha cerrado correctamente y toda la memoria RAM y archivos temporales han sido liberados.
          </p>
          <p style="font-size: 0.85rem; color: #879995; margin: 0;">
            Ya puedes cerrar esta pestaña. Para volver a usar PosterMaker, abre <strong>PosterMaker</strong> desde tu lanzador de aplicaciones.
          </p>
        </div>
      </div>
    `;
  });
}

// ---------- Gestión de actualización automática ----------
const updaterUi = {
  overlay: document.getElementById("updater-overlay"),
  title: document.getElementById("updater-title"),
  desc: document.getElementById("updater-desc"),
  status: document.getElementById("updater-status"),
  btnCheck: document.getElementById("btn-check-update"),
};

async function handleStartupUpdateCheck() {
  if (!updaterUi.overlay) return;

  const hideOverlay = (delay = 350) => {
    setTimeout(() => {
      updaterUi.overlay.classList.add("is-hidden");
    }, delay);
  };

  try {
    const res = await fetch("/api/update/status");
    if (!res.ok) throw new Error("Status failed");
    const state = await res.json();

    if (state.status === "updating") {
      updaterUi.title.textContent = "Actualizando PosterMaker...";
      updaterUi.desc.textContent = state.message || "Descargando e integrando cambios del repositorio...";
      updaterUi.status.textContent = "Aplicando actualización...";

      let attempts = 0;
      const poll = setInterval(async () => {
        attempts++;
        try {
          const pollRes = await fetch("/api/update/status");
          const pollState = await pollRes.json();
          if (pollState.status === "updated") {
            clearInterval(poll);
            updaterUi.title.textContent = "¡Actualización completada!";
            updaterUi.desc.textContent = "PosterMaker está listo con la última versión.";
            updaterUi.status.textContent = "Iniciando...";
            hideOverlay(600);
          } else if (pollState.status === "up_to_date" || pollState.status === "error" || attempts > 15) {
            clearInterval(poll);
            hideOverlay(250);
          }
        } catch (_) {
          clearInterval(poll);
          hideOverlay(250);
        }
      }, 700);
      return;
    } else if (state.status === "updated") {
      updaterUi.title.textContent = "¡PosterMaker actualizado!";
      updaterUi.desc.textContent = state.message;
      updaterUi.status.textContent = "Listo para usar.";
      hideOverlay(500);
      return;
    }

    hideOverlay(250);
  } catch (e) {
    hideOverlay(150);
  }
}

if (updaterUi.btnCheck) {
  updaterUi.btnCheck.addEventListener("click", async () => {
    updaterUi.btnCheck.disabled = true;
    updaterUi.btnCheck.textContent = "Buscando...";
    try {
      const res = await fetch("/api/update/check", { method: "POST" });
      const data = await res.json();
      if (data.status === "updated") {
        alert("¡PosterMaker se ha actualizado correctamente! Recarga la página para ver las novedades.");
        window.location.reload();
      } else if (data.status === "up_to_date") {
        alert(data.message || "PosterMaker ya está en la última versión.");
      } else if (data.status === "available") {
        alert(`Nueva versión disponible: ${data.latest_version}.`);
      } else {
        alert(data.message || "Comprobación completada.");
      }
    } catch (e) {
      alert("No se pudo conectar con el repositorio. Comprueba tu conexión a internet.");
    } finally {
      updaterUi.btnCheck.disabled = false;
      updaterUi.btnCheck.textContent = "Buscar actualizaciones";
    }
  });
}

handleStartupUpdateCheck();

/* ---------- Inicio ---------- */

updateAll();
