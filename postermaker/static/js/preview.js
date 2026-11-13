import { els } from "./dom.js";
import { state } from "./state.js";
import { readOptions } from "./grid.js";

export function drawPreview(grid) {
  if (!state.image) return;

  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  const wrapStyle = getComputedStyle(els.canvasWrap);
  const availableWidth =
    els.canvasWrap.clientWidth -
    parseFloat(wrapStyle.paddingLeft) -
    parseFloat(wrapStyle.paddingRight);

  const availableHeight =
    els.canvasWrap.clientHeight -
    parseFloat(wrapStyle.paddingTop) -
    parseFloat(wrapStyle.paddingBottom);

  if (availableWidth <= 0 || availableHeight <= 0) return;

  const aspect = grid.posterWidth / grid.posterHeight;
  let width, height;

  if (availableWidth / availableHeight > aspect) {
    height = availableHeight;
    width = height * aspect;
  } else {
    width = availableWidth;
    height = width / aspect;
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
