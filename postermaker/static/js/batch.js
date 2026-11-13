import { MAX_UPLOAD_BYTES } from "./constants.js";
import { els } from "./dom.js";
import { state } from "./state.js";
import { setStatus, clearResult, updateAll } from "./ui.js";

export function selectActiveImage(index) {
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

export function removeImage(idx) {
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

export function renderBatchThumbs() {
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

export function showImage(file, image, objectUrl) {
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

export function resetPoster() {
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

export function loadFiles(fileList, append = false) {
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

export function onNewImagesLoaded(newItems, append, startIndex) {
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

export function loadFile(file) {
  if (file) loadFiles([file]);
}
