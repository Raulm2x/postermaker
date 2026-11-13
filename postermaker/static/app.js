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
  fileAddInput: document.getElementById("file-add-input"),
  changeImage: document.getElementById("change-image"),
  previewStage: document.getElementById("preview-stage"),
  batchBar: document.getElementById("batch-bar"),
  batchCount: document.getElementById("batch-count"),
  batchThumbs: document.getElementById("batch-thumbs"),
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
  skipGuide: document.getElementById("skip-guide"),
  separatePosters: document.getElementById("separate-posters"),
  dimensions: document.getElementById("dimensions"),
  summaryDetail: document.getElementById("summary-detail"),
  dpiBadge: document.getElementById("dpi-badge"),
  resolutionNote: document.getElementById("resolution-note"),
  generate: document.getElementById("generate"),
  status: document.getElementById("status"),
  resultCard: document.getElementById("result-card"),
  resultTitle: document.getElementById("result-title"),
  resultDetail: document.getElementById("result-detail"),
  downloadLink: document.getElementById("download-link"),
  downloadZipLink: document.getElementById("download-zip-link"),
  batchSeparateFiles: document.getElementById("batch-separate-files"),
  batchFilesList: document.getElementById("batch-files-list"),
  resultPreview: document.getElementById("result-preview"),
  newPoster: document.getElementById("new-poster"),
  calibrationLink: document.getElementById("calibration-link"),
};

const state = {
  files: [],
  items: [],
  activeIndex: 0,
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
  if (els.batchSeparateFiles) els.batchSeparateFiles.hidden = true;
  if (els.batchFilesList) els.batchFilesList.innerHTML = "";
  els.resultPreview.href = "#";
}

function updateCalibrationLink(paper) {
  if (!els.calibrationLink) return;
  const info = PAPERS[paper] || PAPERS.letter;
  els.calibrationLink.href = `/api/calibration?paper=${encodeURIComponent(paper)}`;
  els.calibrationLink.title = `Descargar hoja de calibración para ${info.name}`;
  els.calibrationLink.textContent = `Calibrar (${info.name})`;
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
  if (state.items && state.items.length > 1) {
    els.imageMeta.textContent = `[${state.activeIndex + 1}/${state.items.length}] ${name} · ${width} × ${height} px`;
  } else {
    els.imageMeta.textContent = `${name} · ${width} × ${height} px`;
  }
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

function selectActiveImage(index) {
  if (!state.items || !state.items[index]) return;
  state.activeIndex = index;
  state.file = state.items[index].file;
  state.image = state.items[index].image;
  state.imageUrl = state.items[index].objectUrl;
  state.invalid = false;

  if (els.batchThumbs) {
    const thumbs = els.batchThumbs.querySelectorAll(".batch-thumb-item");
    thumbs.forEach((el, i) => el.classList.toggle("is-active", i === index));
  }
  updateAll();
}

function removeImage(idx) {
  if (!state.items || !state.items[idx]) return;
  if (state.items[idx].objectUrl) {
    URL.revokeObjectURL(state.items[idx].objectUrl);
  }
  state.items.splice(idx, 1);
  state.files = state.items.map((it) => it.file);

  if (state.items.length === 0) {
    resetPoster();
    return;
  }

  if (state.activeIndex >= state.items.length) {
    state.activeIndex = state.items.length - 1;
  }
  selectActiveImage(state.activeIndex);
  renderBatchThumbs();
  clearResult();
  updateAll();
}

function renderBatchThumbs() {
  if (!els.batchBar || !els.batchThumbs) return;
  if (!state.items || state.items.length === 0) {
    els.batchBar.hidden = true;
    return;
  }

  els.batchBar.hidden = false;
  const count = state.items.length;
  if (els.batchCount) {
    els.batchCount.textContent = `${count} ${count === 1 ? "imagen" : "imágenes"}`;
  }
  els.batchThumbs.innerHTML = "";

  state.items.forEach((item, idx) => {
    const thumb = document.createElement("div");
    thumb.className = `batch-thumb-item ${idx === state.activeIndex ? "is-active" : ""}`;
    thumb.title = `${idx + 1}. ${item.file.name}`;
    thumb.innerHTML = `
      <span class="batch-thumb-num">${idx + 1}</span>
      <img src="${item.objectUrl}" alt="${item.file.name}" />
      <button type="button" class="batch-thumb-remove" title="Quitar de la lista" aria-label="Quitar">&times;</button>
    `;
    thumb.addEventListener("click", (e) => {
      if (e.target.closest(".batch-thumb-remove")) {
        e.preventDefault();
        e.stopPropagation();
        removeImage(idx);
        return;
      }
      selectActiveImage(idx);
    });
    els.batchThumbs.appendChild(thumb);
  });

  const addBtn = document.createElement("button");
  addBtn.type = "button";
  addBtn.className = "batch-thumb-add";
  addBtn.title = "Añadir más imágenes";
  addBtn.innerHTML = `
    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2">
      <path d="M8 3v10M3 8h10"/>
    </svg>
    <span>Añadir</span>
  `;
  addBtn.addEventListener("click", (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (els.fileAddInput) els.fileAddInput.click();
  });
  els.batchThumbs.appendChild(addBtn);
}

function showImage(file, image, objectUrl) {
  if (state.imageUrl) {
    URL.revokeObjectURL(state.imageUrl);
  }
  state.files = [file];
  state.items = [{ file, image, objectUrl }];
  state.activeIndex = 0;
  state.file = file;
  state.image = image;
  state.imageUrl = objectUrl;
  state.invalid = false;

  els.dropzone.hidden = true;
  els.previewStage.hidden = false;
  if (els.batchBar) els.batchBar.hidden = true;
  if (els.changeImage) els.changeImage.hidden = false;
  clearResult();
  setStatus("");
  updateAll();
}

function resetPoster() {
  if (state.items) {
    for (const item of state.items) {
      if (item && item.objectUrl) URL.revokeObjectURL(item.objectUrl);
    }
  }
  if (state.imageUrl) {
    URL.revokeObjectURL(state.imageUrl);
  }
  state.files = [];
  state.items = [];
  state.activeIndex = 0;
  state.file = null;
  state.image = null;
  state.imageUrl = null;
  state.generating = false;
  state.invalid = false;

  if (els.fileInput) els.fileInput.value = "";
  if (els.fileAddInput) els.fileAddInput.value = "";
  els.dropzone.hidden = false;
  els.previewStage.hidden = true;
  if (els.batchBar) els.batchBar.hidden = true;
  if (els.batchThumbs) els.batchThumbs.innerHTML = "";
  if (els.changeImage) els.changeImage.hidden = true;
  els.generate.classList.remove("loading");
  els.generate.removeAttribute("aria-busy");
  els.generate.querySelector(".button-label").textContent = "Crear PDF";
  clearResult();
  setStatus("");
  updateAll();
}

function loadFiles(fileList, append = false) {
  if (!fileList || !fileList.length) return;
  const files = Array.from(fileList);

  const validFiles = [];
  for (const file of files) {
    const isImage =
      ["image/jpeg", "image/png", "image/webp"].includes(file.type) ||
      /\.(jpe?g|png|webp)$/i.test(file.name);
    if (!isImage) {
      setStatus(`El archivo "${file.name}" no es compatible. Usa JPG, PNG o WebP.`, "error");
      continue;
    }
    if (file.size > MAX_UPLOAD_BYTES) {
      setStatus(`El archivo "${file.name}" supera el límite de 25 MB.`, "error");
      continue;
    }
    validFiles.push(file);
  }

  if (!validFiles.length) return;

  if (!append) {
    if (state.items) {
      for (const item of state.items) {
        if (item && item.objectUrl) URL.revokeObjectURL(item.objectUrl);
      }
    }
    if (state.imageUrl) {
      URL.revokeObjectURL(state.imageUrl);
    }
    state.items = [];
    state.files = [];
  }

  const startIndex = state.items.length;
  const newItems = new Array(validFiles.length);
  let loadedCount = 0;
  const total = validFiles.length;

  validFiles.forEach((file, index) => {
    const objectUrl = URL.createObjectURL(file);
    const img = new Image();
    img.onload = () => {
      newItems[index] = { file, image: img, objectUrl };
      loadedCount += 1;
      if (loadedCount === total) {
        onNewImagesLoaded(newItems, append, startIndex);
      }
    };
    img.onerror = () => {
      URL.revokeObjectURL(objectUrl);
      loadedCount += 1;
      if (loadedCount === total) {
        onNewImagesLoaded(newItems, append, startIndex);
      }
    };
    img.src = objectUrl;
  });
}

function onNewImagesLoaded(newItems, append, startIndex) {
  const filtered = newItems.filter(Boolean);
  if (!filtered.length) {
    if (!state.items.length) {
      setStatus("No se pudieron cargar las imágenes seleccionadas.", "error");
    }
    return;
  }

  if (append) {
    state.items = state.items.concat(filtered);
  } else {
    state.items = filtered;
  }
  state.files = state.items.map((it) => it.file);

  const targetIndex = append ? startIndex : 0;
  state.activeIndex = targetIndex;
  state.file = state.items[targetIndex].file;
  state.image = state.items[targetIndex].image;
  state.imageUrl = state.items[targetIndex].objectUrl;
  state.invalid = false;

  els.dropzone.hidden = true;
  els.previewStage.hidden = false;
  if (els.changeImage) els.changeImage.hidden = false;

  renderBatchThumbs();
  clearResult();
  setStatus("");
  updateAll();
}

function loadFile(file) {
  if (file) loadFiles([file]);
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

async function generate() {
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

/* ---------- Eventos ---------- */

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

// Botón de apagado manual
const shutdownBtn = document.getElementById("btn-shutdown");
if (shutdownBtn) {
  shutdownBtn.addEventListener("click", async () => {
    const confirmShutdown = window.confirm(
      "¿Deseas salir de PosterMaker y cerrar la aplicación?"
    );
    if (!confirmShutdown) return;

    shutdownBtn.disabled = true;
    shutdownBtn.textContent = "Cerrando...";

    try {
      await fetch("/api/shutdown", { method: "POST" });
    } catch (e) {
      // Proceso terminado
    }

    document.body.innerHTML = `
      <div style="min-height: 100vh; display: flex; flex-direction: column; align-items: center; justify-content: center; font-family: system-ui, -apple-system, sans-serif; text-align: center; padding: 24px; background: #fffdf8; color: #17211f;">
        <div style="max-width: 440px; background: #ffffff; border: 1px solid rgba(23,33,31,0.12); border-radius: 14px; padding: 36px 28px; box-shadow: 0 10px 30px rgba(0,0,0,0.06);">
          <h1 style="font-size: 1.3rem; font-weight: 600; margin-bottom: 12px; color: #17211f;">PosterMaker se ha cerrado</h1>
          <p style="font-size: 0.95rem; color: #526360; line-height: 1.5; margin: 0;">
            Ya puedes cerrar esta pestaña. Para volver a usar la aplicación, iníciala desde tu lanzador de programas.
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

async function triggerUpdateApply(targetVersion) {
  if (updaterUi.overlay) {
    updaterUi.overlay.classList.remove("is-hidden");
    updaterUi.title.textContent = "Actualizando PosterMaker...";
    updaterUi.desc.textContent = targetVersion
      ? `Descargando e integrando la versión v${targetVersion}...`
      : "Descargando e integrando los cambios...";
    updaterUi.status.textContent = "Por favor espera mientras se aplica la actualización...";
  }

  try {
    const applyRes = await fetch("/api/update/apply", { method: "POST" });
    const applyData = await applyRes.json();

    if (applyData.status === "updated" || applyData.ok !== false) {
      if (updaterUi.title) updaterUi.title.textContent = "¡Actualización completada!";
      if (updaterUi.desc) updaterUi.desc.textContent = "PosterMaker se ha actualizado correctamente. Reiniciando...";
      if (updaterUi.status) updaterUi.status.textContent = "Recargando interfaz...";

      setTimeout(() => {
        window.location.reload();
      }, 2000);
    } else {
      if (updaterUi.overlay) updaterUi.overlay.classList.add("is-hidden");
      alert(applyData.message || applyData.error || "No se pudo completar la actualización.");
    }
  } catch (err) {
    // En caso de que el reinicio del servidor corte la conexión
    if (updaterUi.status) updaterUi.status.textContent = "Servidor reiniciado. Recargando...";
    setTimeout(() => {
      window.location.reload();
    }, 2000);
  }
}

async function handleStartupUpdateCheck() {
  try {
    const res = await fetch("/api/update/status");
    if (!res.ok) throw new Error("Status failed");
    const state = await res.json();

    if (state.status === "updating" && updaterUi.overlay) {
      updaterUi.overlay.classList.remove("is-hidden");
      updaterUi.title.textContent = "Actualizando PosterMaker...";
      updaterUi.desc.textContent = state.message || "Descargando e integrando cambios...";
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
            setTimeout(() => window.location.reload(), 1000);
          } else if (pollState.status === "up_to_date" || pollState.status === "error" || attempts > 20) {
            clearInterval(poll);
            if (updaterUi.overlay) updaterUi.overlay.classList.add("is-hidden");
          }
        } catch (_) {
          clearInterval(poll);
          if (updaterUi.overlay) updaterUi.overlay.classList.add("is-hidden");
        }
      }, 700);
      return;
    } else if (state.status === "available" || state.has_update) {
      if (updaterUi.btnCheck) {
        updaterUi.btnCheck.textContent = `Actualizar a v${state.latest_version}`;
        updaterUi.btnCheck.style.fontWeight = "600";
        updaterUi.btnCheck.style.color = "#e4572e";
      }
    }
  } catch (e) {
    // Silencioso en modo local / sin conexión
  }
}

if (updaterUi.btnCheck) {
  updaterUi.btnCheck.addEventListener("click", async () => {
    updaterUi.btnCheck.disabled = true;
    updaterUi.btnCheck.textContent = "Buscando...";
    try {
      const res = await fetch("/api/update/check", { method: "POST" });
      const data = await res.json();
      if (data.status === "available" || data.has_update) {
        const confirmUpdate = confirm(
          `Nueva versión disponible: v${data.latest_version || data.current_version}.\n\n` +
          `¿Deseas descargar e instalar la actualización ahora?`
        );
        if (confirmUpdate) {
          await triggerUpdateApply(data.latest_version);
        }
      } else if (data.status === "updated") {
        alert("¡PosterMaker se ha actualizado correctamente! Recargando la página...");
        window.location.reload();
      } else if (data.status === "up_to_date") {
        alert(data.message || "PosterMaker ya está en la última versión.");
      } else {
        alert(data.message || "Comprobación completada.");
      }
    } catch (e) {
      alert("No se pudo conectar con el servidor para comprobar actualizaciones.");
    } finally {
      updaterUi.btnCheck.disabled = false;
      if (!updaterUi.btnCheck.textContent.includes("Actualizar a")) {
        updaterUi.btnCheck.textContent = "Buscar actualizaciones";
      }
    }
  });
}

handleStartupUpdateCheck();

/* ---------- Inicio ---------- */

updateAll();
