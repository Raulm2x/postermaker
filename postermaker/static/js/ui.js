import { PAPERS, MAX_TOTAL_PAGES } from "./constants.js";
import { els } from "./dom.js";
import { state } from "./state.js";
import { decimal, formatBytes } from "./formatters.js";
import { readOptions, computeGrid } from "./grid.js";
import { drawPreview } from "./preview.js";

export function setStatus(message, type = "") {
  els.status.textContent = message;
  els.status.className = `status ${type}`.trim();
  els.status.hidden = !message;
}

export function clearResult() {
  els.resultCard.hidden = true;
  els.downloadLink.href = "#";
  if (els.downloadZipLink) els.downloadZipLink.href = "#";
  if (els.batchSeparateFiles) els.batchSeparateFiles.hidden = true;
  if (els.batchFilesList) els.batchFilesList.innerHTML = "";
  els.resultPreview.href = "#";
}

export function updateCalibrationLink(paper) {
  if (!els.calibrationLink) return;
  const info = PAPERS[paper] || PAPERS.letter;
  els.calibrationLink.href = `/api/calibration?paper=${encodeURIComponent(paper)}`;
  els.calibrationLink.title = `Descargar hoja de calibración para ${info.name}`;
  els.calibrationLink.textContent = `Calibrar (${info.name})`;
}

export function updateLabels(options) {
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

export function updateSummary(options, grid) {
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
  const totalPages = grid.totalPages + (options.guide ? 1 : 0);

  if (state.items && state.items.length > 1) {
    const isSep = options.separatePosters;
    const modeText = isSep ? "pósteres por separado" : "1 PDF combinado";
    els.summaryDetail.textContent =
      `${state.items.length} imágenes cargadas (${modeText}) · ` +
      `activa: ${grid.pagesWide} × ${grid.pagesHigh} hojas · ` +
      `${totalPages} pág${totalPages === 1 ? "" : "s"}` +
      (partialRow ? " · fila parcial" : "");

    if (!state.generating) {
      els.generate.querySelector(".button-label").textContent = isSep
        ? `Crear ${state.items.length} pósteres por separado`
        : `Crear PDF combinado (${state.items.length} pósteres)`;
    }
  } else {
    els.summaryDetail.textContent =
      `${grid.pagesWide} × ${grid.pagesHigh} hojas · ` +
      `${totalPages} página${totalPages === 1 ? "" : "s"} · ` +
      `${(PAPERS[options.paper] || PAPERS.letter).name} ${orientationText}` +
      (partialRow ? " · última fila parcial" : "");

    if (!state.generating) {
      els.generate.querySelector(".button-label").textContent = "Crear PDF";
    }
  }

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

export function updateImageMeta() {
  if (!state.file || !state.image) {
    els.imageMeta.textContent = "—";
    return;
  }
  const name = state.file.name;
  const width = state.image.naturalWidth;
  const height = state.image.naturalHeight;
  if (state.items && state.items.length > 1) {
    els.imageMeta.textContent = `[${state.activeIndex + 1}/${state.items.length}] ${name} · ${width} × ${height} px`;
  } else {
    els.imageMeta.textContent = `${name} · ${width} × ${height} px`;
  }
}

export function updateAll() {
  const options = readOptions();
  const grid = computeGrid(options);
  updateSummary(options, grid);
  updateImageMeta();

  if (state.image) {
    requestAnimationFrame(() => drawPreview(grid));
  }
}

export function setGenerating(value) {
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

export function showResult(data) {
  clearResult();

  const size = formatBytes(data.sizeBytes);
  if (data.isBatch) {
    if (data.separate) {
      if (els.resultTitle) els.resultTitle.textContent = "Tus pósteres están listos";
      els.resultDetail.textContent =
        `${data.posterCount} pósteres generados por separado · ${data.totalPages} páginas totales` +
        (size ? ` · ZIP ${size}` : "");

      els.downloadLink.href = data.downloadUrl;
      els.downloadLink.setAttribute("download", data.filename || "posters_separados.zip");
      els.downloadLink.querySelector(".download-label").textContent = size
        ? `Descargar todos los pósteres (ZIP ${size})`
        : "Descargar pósteres (ZIP)";

      if (els.batchSeparateFiles && els.batchFilesList && data.items && data.items.length) {
        els.batchFilesList.innerHTML = "";
        data.items.forEach((item) => {
          const row = document.createElement("div");
          row.className = "batch-file-row";
          const itemSize = formatBytes(item.sizeBytes);
          row.innerHTML = `
            <div class="batch-file-info">
              <span class="batch-file-name" title="${item.filename}">${item.filename}</span>
              <span class="batch-file-meta">${item.pagesWide} × ${item.pagesHigh} hojas · ${item.totalPages} páginas${itemSize ? " · " + itemSize : ""}</span>
            </div>
            <a class="batch-file-btn" href="${item.downloadUrl}" download="${item.filename}">
              Descargar PDF
            </a>
          `;
          els.batchFilesList.appendChild(row);
        });
        els.batchSeparateFiles.hidden = false;
      }
    } else {
      if (els.resultTitle) els.resultTitle.textContent = "Tu PDF combinado está listo";
      els.resultDetail.textContent =
        `${data.posterCount} pósteres combinados · ${data.totalPages} páginas totales` +
        (size ? ` · ${size}` : "");

      els.downloadLink.href = data.downloadUrl;
      els.downloadLink.setAttribute("download", data.filename || "posters_combinados.pdf");
      els.downloadLink.querySelector(".download-label").textContent = size
        ? `Descargar PDF combinado (${size})`
        : "Descargar PDF combinado";

      if (els.batchSeparateFiles) els.batchSeparateFiles.hidden = true;
    }
  } else {
    if (els.resultTitle) els.resultTitle.textContent = "Tu PDF está listo";
    els.resultDetail.textContent =
      `${data.pagesWide} × ${data.pagesHigh} hojas · ` +
      `${decimal.format(data.widthCm)} × ${decimal.format(data.heightCm)} cm` +
      (size ? ` · ${size}` : "");

    els.downloadLink.href = data.downloadUrl;
    els.downloadLink.setAttribute("download", data.filename || "poster.pdf");
    els.downloadLink.querySelector(".download-label").textContent = size
      ? `Descargar PDF (${size})`
      : "Descargar PDF";

    if (els.batchSeparateFiles) els.batchSeparateFiles.hidden = true;
  }

  if (els.downloadZipLink) {
    els.downloadZipLink.href = data.downloadZipUrl || `/api/download/${data.id}/zip`;
    const base = (data.filename || "poster.pdf").replace(/\.(pdf|zip)$/i, "");
    els.downloadZipLink.setAttribute("download", `${base}_piezas.zip`);
  }

  els.resultPreview.href = data.previewUrl;
  els.resultCard.hidden = false;
  els.resultCard.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

export async function generate() {
  const filesToUpload = (state.files && state.files.length) ? state.files : (state.file ? [state.file] : []);
  if (!filesToUpload.length || state.generating || state.invalid) return;

  const options = readOptions();
  const formData = new FormData();
  for (const f of filesToUpload) {
    formData.append("image", f, f.name);
  }
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
  formData.append("skip_guide", options.skipGuide ? "true" : "false");
  formData.append("separate_posters", options.separatePosters ? "true" : "false");

  setGenerating(true);
  const msg = filesToUpload.length > 1
    ? (options.separatePosters
        ? `Generando ${filesToUpload.length} pósteres por separado…`
        : `Generando PDF combinado de ${filesToUpload.length} pósteres…`)
    : "Generando el PDF. Las imágenes grandes pueden tardar unos segundos…";
  setStatus(msg);
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
