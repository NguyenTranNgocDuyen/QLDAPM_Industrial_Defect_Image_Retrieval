/**
 * Keyboard Annotation Studio - Frontend Logic
 */

// State
let images = [];
let currentIndex = 0;
let currentImage = null; // HTMLImageElement
let boxes = []; // Array of { id, cls, cx, cy, w, h }
let selectedBoxIndex = -1;
let currentTool = "select"; // "select" | "draw"
let activeClass = 0; // 0: key_ok, 1: key_damaged, 2: key_missing
let isDirty = false;

// Canvas & Viewport State
const canvas = document.getElementById("mainCanvas");
const ctx = canvas.getContext("2d");
const viewport = document.getElementById("canvasViewport");

let scale = 1.0;
let isDrawing = false;
let drawStartX = 0;
let drawStartY = 0;
let currentDrawBox = null;

let isDragging = false;
let dragStartX = 0;
let dragStartY = 0;
let dragBoxStart = null;

const CLASS_CONFIG = {
  0: { name: "key_ok", color: "#10b981", bg: "rgba(16, 185, 129, 0.2)", label: "OK" },
  1: { name: "key_damaged", color: "#ef4444", bg: "rgba(239, 68, 68, 0.3)", label: "HỎNG" },
  2: { name: "key_missing", color: "#f59e0b", bg: "rgba(245, 158, 11, 0.3)", label: "MẤT" }
};

// Elements
const datasetSelect = document.getElementById("datasetSelect");
const splitSelect = document.getElementById("splitSelect");
const filterSelect = document.getElementById("filterSelect");
const saveBtn = document.getElementById("saveBtn");
const saveStatus = document.getElementById("saveStatus");
const prevBtn = document.getElementById("prevBtn");
const nextBtn = document.getElementById("nextBtn");
const imageCounter = document.getElementById("imageCounter");
const currentImageName = document.getElementById("currentImageName");
const boxList = document.getElementById("boxList");
const totalBoxBadge = document.getElementById("totalBoxBadge");
const okCountEl = document.getElementById("okCount");
const damagedCountEl = document.getElementById("damagedCount");
const missingCountEl = document.getElementById("missingCount");
const loadingOverlay = document.getElementById("loadingOverlay");
const deleteBoxBtn = document.getElementById("deleteBoxBtn");
const resetZoomBtn = document.getElementById("resetZoomBtn");
const deleteImageBtn = document.getElementById("deleteImageBtn");
const autoDedupBtn = document.getElementById("autoDedupBtn");

const toolSelect = document.getElementById("toolSelect");
const toolDraw = document.getElementById("toolDraw");
const btnClassOk = document.getElementById("btnClassOk");
const btnClassDamaged = document.getElementById("btnClassDamaged");
const btnClassMissing = document.getElementById("btnClassMissing");

// Initialize
window.addEventListener("DOMContentLoaded", () => {
  setupEventListeners();
  loadImages();
});

function setupEventListeners() {
  datasetSelect.addEventListener("change", () => loadImages());
  splitSelect.addEventListener("change", () => loadImages());
  filterSelect.addEventListener("change", () => loadImages());

  prevBtn.addEventListener("click", () => navigate(-1));
  nextBtn.addEventListener("click", () => navigate(1));
  saveBtn.addEventListener("click", () => saveLabels());

  toolSelect.addEventListener("click", () => setTool("select"));
  toolDraw.addEventListener("click", () => setTool("draw"));

  btnClassOk.addEventListener("click", () => setActiveClass(0));
  btnClassDamaged.addEventListener("click", () => setActiveClass(1));
  btnClassMissing.addEventListener("click", () => setActiveClass(2));

  deleteBoxBtn.addEventListener("click", () => deleteSelectedBox());
  resetZoomBtn.addEventListener("click", () => fitImageToViewport());
  deleteImageBtn.addEventListener("click", () => deleteCurrentImage());
  autoDedupBtn.addEventListener("click", () => autoDeduplicateDataset());

  // Canvas Mouse Events
  canvas.addEventListener("mousedown", onCanvasMouseDown);
  window.addEventListener("mousemove", onCanvasMouseMove);
  window.addEventListener("mouseup", onCanvasMouseUp);

  // Keyboard Shortcuts
  window.addEventListener("keydown", (e) => {
    // Ignore input fields
    if (e.target.tagName === "INPUT" || e.target.tagName === "SELECT") return;

    if (e.key === "a" || e.key === "A" || e.key === "ArrowLeft") {
      navigate(-1);
    } else if (e.key === "d" || e.key === "D" || e.key === "ArrowRight") {
      navigate(1);
    } else if (e.key === "1") {
      setActiveClass(0);
      if (selectedBoxIndex >= 0) changeSelectedBoxClass(0);
    } else if (e.key === "2") {
      setActiveClass(1);
      if (selectedBoxIndex >= 0) changeSelectedBoxClass(1);
    } else if (e.key === "3") {
      setActiveClass(2);
      if (selectedBoxIndex >= 0) changeSelectedBoxClass(2);
    } else if (e.shiftKey && (e.key === "Delete" || e.key === "Backspace")) {
      e.preventDefault();
      deleteCurrentImage();
    } else if (e.key === "Delete" || e.key === "Backspace") {
      deleteSelectedBox();
    } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") {
      e.preventDefault();
      saveLabels();
    } else if (e.key.toLowerCase() === "v") {
      setTool("select");
    } else if (e.key.toLowerCase() === "r") {
      setTool("draw");
    }
  });

  window.addEventListener("resize", () => {
    if (currentImage) fitImageToViewport();
  });
}

function setTool(tool) {
  currentTool = tool;
  toolSelect.classList.toggle("bg-gray-800", tool === "select");
  toolSelect.classList.toggle("text-indigo-400", tool === "select");
  toolDraw.classList.toggle("bg-gray-800", tool === "draw");
  toolDraw.classList.toggle("text-indigo-400", tool === "draw");
}

function setActiveClass(clsId) {
  activeClass = clsId;
  const btns = [btnClassOk, btnClassDamaged, btnClassMissing];
  btns.forEach((btn, idx) => {
    btn.classList.toggle("border-2", idx === clsId);
    btn.classList.toggle("border", idx !== clsId);
    if (idx === 0) btn.classList.toggle("border-emerald-500", idx === clsId);
    if (idx === 1) btn.classList.toggle("border-red-500", idx === clsId);
    if (idx === 2) btn.classList.toggle("border-amber-500", idx === clsId);
  });
}

function changeSelectedBoxClass(newCls) {
  if (selectedBoxIndex >= 0 && selectedBoxIndex < boxes.length) {
    boxes[selectedBoxIndex].cls = newCls;
    markDirty();
    render();
    renderBoxList();
  }
}

function deleteSelectedBox() {
  if (selectedBoxIndex >= 0 && selectedBoxIndex < boxes.length) {
    boxes.splice(selectedBoxIndex, 1);
    selectedBoxIndex = -1;
    markDirty();
    render();
    renderBoxList();
  }
}

function markDirty() {
  isDirty = true;
  saveStatus.innerHTML = `<i class="fa-solid fa-circle-exclamation text-amber-500 mr-1.5"></i> Chưa lưu`;
}

function markClean() {
  isDirty = false;
  saveStatus.innerHTML = `<i class="fa-solid fa-check text-green-500 mr-1.5"></i> Đã đồng bộ`;
}

async function loadImages() {
  loadingOverlay.classList.remove("hidden");
  const dataset = datasetSelect.value;
  const split = splitSelect.value;
  const filter = filterSelect.value;

  try {
    const res = await fetch(`/api/images?dataset=${dataset}&split=${split}&filter=${filter}`);
    images = await res.json();
    currentIndex = 0;
    if (images.length > 0) {
      await loadImageAndLabels(currentIndex);
    } else {
      currentImage = null;
      boxes = [];
      render();
      imageCounter.innerText = "0 / 0";
      currentImageName.innerText = "Không có ảnh nào khớp bộ lọc";
    }
  } catch (err) {
    console.error("Error loading images:", err);
  } finally {
    loadingOverlay.classList.add("hidden");
  }
}

async function loadImageAndLabels(index) {
  if (index < 0 || index >= images.length) return;
  loadingOverlay.classList.remove("hidden");

  const item = images[index];
  const dataset = datasetSelect.value;
  const split = splitSelect.value;

  currentImageName.innerText = item.name;
  currentImageName.title = item.name;
  imageCounter.innerText = `${index + 1} / ${images.length}`;

  try {
    // 1. Load image
    const imgUrl = `/api/image/${dataset}/${split}/${item.name}`;
    const img = new Image();
    await new Promise((resolve, reject) => {
      img.onload = resolve;
      img.onerror = reject;
      img.src = imgUrl;
    });
    currentImage = img;

    // 2. Load labels
    const res = await fetch(`/api/labels/${dataset}/${split}/${item.name}`);
    const data = await res.json();
    boxes = data.boxes || [];
    selectedBoxIndex = -1;
    markClean();

    fitImageToViewport();
    renderBoxList();
  } catch (err) {
    console.error("Error loading image/labels:", err);
  } finally {
    loadingOverlay.classList.add("hidden");
  }
}

function fitImageToViewport() {
  if (!currentImage) return;
  const rect = viewport.getBoundingClientRect();
  const maxW = rect.width - 40;
  const maxH = rect.height - 40;

  scale = Math.min(maxW / currentImage.width, maxH / currentImage.height, 1.5);
  canvas.width = currentImage.width * scale;
  canvas.height = currentImage.height * scale;

  render();
}

function render() {
  if (!currentImage) {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    return;
  }

  ctx.clearRect(0, 0, canvas.width, canvas.height);
  // Draw base image
  ctx.drawImage(currentImage, 0, 0, canvas.width, canvas.height);

  let ok = 0, damaged = 0, missing = 0;

  // Draw boxes
  boxes.forEach((b, idx) => {
    if (b.cls === 0) ok++;
    else if (b.cls === 1) damaged++;
    else if (b.cls === 2) missing++;

    const conf = CLASS_CONFIG[b.cls] || CLASS_CONFIG[0];
    const isSelected = idx === selectedBoxIndex;

    const x = (b.cx - b.w / 2) * canvas.width;
    const y = (b.cy - b.h / 2) * canvas.height;
    const w = b.w * canvas.width;
    const h = b.h * canvas.height;

    // Fill
    ctx.fillStyle = isSelected ? "rgba(99, 102, 241, 0.35)" : conf.bg;
    ctx.fillRect(x, y, w, h);

    // Border
    ctx.strokeStyle = isSelected ? "#ffffff" : conf.color;
    ctx.lineWidth = isSelected ? 2.5 : 1.5;
    ctx.strokeRect(x, y, w, h);

    // Small label tag
    ctx.fillStyle = isSelected ? "#6366f1" : conf.color;
    ctx.fillRect(x, Math.max(0, y - 14), Math.min(w, 24), 14);
    ctx.fillStyle = "#ffffff";
    ctx.font = "bold 9px sans-serif";
    ctx.fillText(conf.label, x + 3, Math.max(10, y - 3));
  });

  // Current drawing box
  if (isDrawing && currentDrawBox) {
    const conf = CLASS_CONFIG[activeClass] || CLASS_CONFIG[0];
    ctx.fillStyle = conf.bg;
    ctx.fillRect(currentDrawBox.x, currentDrawBox.y, currentDrawBox.w, currentDrawBox.h);
    ctx.strokeStyle = conf.color;
    ctx.lineWidth = 2;
    ctx.setLineDash([4, 4]);
    ctx.strokeRect(currentDrawBox.x, currentDrawBox.y, currentDrawBox.w, currentDrawBox.h);
    ctx.setLineDash([]);
  }

  // Update counts
  okCountEl.innerText = ok;
  damagedCountEl.innerText = damaged;
  missingCountEl.innerText = missing;
  totalBoxBadge.innerText = boxes.length;
}

function renderBoxList() {
  boxList.innerHTML = "";
  boxes.forEach((b, idx) => {
    const conf = CLASS_CONFIG[b.cls] || CLASS_CONFIG[0];
    const isSelected = idx === selectedBoxIndex;

    const div = document.createElement("div");
    div.className = `p-2 rounded border flex items-center justify-between cursor-pointer transition ${
      isSelected ? "bg-indigo-950/60 border-indigo-500" : "bg-gray-800/60 border-gray-700/60 hover:bg-gray-800"
    }`;

    div.innerHTML = `
      <div class="flex items-center space-x-2">
        <span class="w-2.5 h-2.5 rounded-full" style="background-color: ${conf.color}"></span>
        <span class="font-medium text-gray-200">#${idx + 1} ${conf.name}</span>
      </div>
      <div class="flex items-center space-x-1">
        <button class="text-gray-400 hover:text-red-400 px-1 delete-single" title="Xóa">
          <i class="fa-solid fa-xmark"></i>
        </button>
      </div>
    `;

    div.addEventListener("click", (e) => {
      if (e.target.closest(".delete-single")) {
        boxes.splice(idx, 1);
        selectedBoxIndex = -1;
        markDirty();
        render();
        renderBoxList();
      } else {
        selectedBoxIndex = idx;
        render();
        renderBoxList();
      }
    });

    boxList.appendChild(div);
  });
}

function onCanvasMouseDown(e) {
  if (!currentImage) return;
  const rect = canvas.getBoundingClientRect();
  const mouseX = e.clientX - rect.left;
  const mouseY = e.clientY - rect.top;

  if (currentTool === "draw") {
    isDrawing = true;
    drawStartX = mouseX;
    drawStartY = mouseY;
    currentDrawBox = { x: mouseX, y: mouseY, w: 0, h: 0 };
  } else {
    // Select tool: Check click inside box
    let clickedIndex = -1;
    // Iterate in reverse so topmost box gets picked
    for (let i = boxes.length - 1; i >= 0; i--) {
      const b = boxes[i];
      const x = (b.cx - b.w / 2) * canvas.width;
      const y = (b.cy - b.h / 2) * canvas.height;
      const w = b.w * canvas.width;
      const h = b.h * canvas.height;

      if (mouseX >= x && mouseX <= x + w && mouseY >= y && mouseY <= y + h) {
        clickedIndex = i;
        break;
      }
    }

    selectedBoxIndex = clickedIndex;
    if (selectedBoxIndex >= 0) {
      isDragging = true;
      dragStartX = mouseX;
      dragStartY = mouseY;
      dragBoxStart = { ...boxes[selectedBoxIndex] };
    }
    render();
    renderBoxList();
  }
}

function onCanvasMouseMove(e) {
  if (!currentImage) return;
  const rect = canvas.getBoundingClientRect();
  const mouseX = e.clientX - rect.left;
  const mouseY = e.clientY - rect.top;

  if (isDrawing) {
    const x = Math.min(drawStartX, mouseX);
    const y = Math.min(drawStartY, mouseY);
    const w = Math.abs(mouseX - drawStartX);
    const h = Math.abs(mouseY - drawStartY);
    currentDrawBox = { x, y, w, h };
    render();
  } else if (isDragging && selectedBoxIndex >= 0 && dragBoxStart) {
    const dx = (mouseX - dragStartX) / canvas.width;
    const dy = (mouseY - dragStartY) / canvas.height;

    boxes[selectedBoxIndex].cx = Math.max(0, Math.min(1, dragBoxStart.cx + dx));
    boxes[selectedBoxIndex].cy = Math.max(0, Math.min(1, dragBoxStart.cy + dy));
    markDirty();
    render();
  }
}

function onCanvasMouseUp(e) {
  if (isDrawing && currentDrawBox) {
    isDrawing = false;
    if (currentDrawBox.w > 8 && currentDrawBox.h > 8) {
      const cx = (currentDrawBox.x + currentDrawBox.w / 2) / canvas.width;
      const cy = (currentDrawBox.y + currentDrawBox.h / 2) / canvas.height;
      const w = currentDrawBox.w / canvas.width;
      const h = currentDrawBox.h / canvas.height;

      boxes.push({
        id: boxes.length + 1,
        cls: activeClass,
        cx, cy, w, h
      });
      selectedBoxIndex = boxes.length - 1;
      markDirty();
      renderBoxList();
    }
    currentDrawBox = null;
    render();
  }

  isDragging = false;
  dragBoxStart = null;
}

async function navigate(delta) {
  if (isDirty) {
    if (confirm("Bạn có thay đổi chưa lưu! Bạn có muốn lưu trước khi chuyển ảnh không?")) {
      await saveLabels();
    }
  }

  const nextIdx = currentIndex + delta;
  if (nextIdx >= 0 && nextIdx < images.length) {
    currentIndex = nextIdx;
    await loadImageAndLabels(currentIndex);
  }
}

async function saveLabels() {
  if (!currentImage || images.length === 0) return;
  const item = images[currentIndex];
  const dataset = datasetSelect.value;
  const split = splitSelect.value;

  try {
    saveBtn.disabled = true;
    saveBtn.innerHTML = `<i class="fa-solid fa-spinner fa-spin mr-1.5"></i> Đang lưu...`;

    const res = await fetch(`/api/labels/${dataset}/${split}/${item.name}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ boxes })
    });

    if (res.ok) {
      markClean();
      saveBtn.innerHTML = `<i class="fa-solid fa-check mr-1.5"></i> Đã lưu!`;
      setTimeout(() => {
        saveBtn.innerHTML = `<i class="fa-solid fa-floppy-disk mr-1.5"></i> Lưu (Ctrl+S)`;
        saveBtn.disabled = false;
      }, 1000);
    }
  } catch (err) {
    console.error("Error saving labels:", err);
    alert("Có lỗi khi lưu nhãn!");
    saveBtn.disabled = false;
  }
}

async function deleteCurrentImage() {
  if (!currentImage || images.length === 0) return;
  const item = images[currentIndex];
  const dataset = datasetSelect.value;
  const split = splitSelect.value;

  if (!confirm(`Bạn có chắc chắn muốn xóa ảnh "${item.name}" và chuyển vào thư mục deleted không?`)) {
    return;
  }

  try {
    deleteImageBtn.disabled = true;
    deleteImageBtn.innerHTML = `<i class="fa-solid fa-spinner fa-spin mr-1.5"></i> Đang xóa...`;

    const res = await fetch(`/api/delete_image/${dataset}/${split}/${item.name}`, {
      method: "POST"
    });

    if (res.ok) {
      // Remove from local list
      images.splice(currentIndex, 1);
      markClean();

      deleteImageBtn.innerHTML = `<i class="fa-solid fa-check mr-1.5"></i> Đã xóa!`;
      setTimeout(() => {
        deleteImageBtn.innerHTML = `<i class="fa-solid fa-trash-can mr-1.5"></i> Xóa ảnh (Shift+Del)`;
        deleteImageBtn.disabled = false;
      }, 800);

      if (images.length === 0) {
        currentImage = null;
        boxes = [];
        render();
        imageCounter.innerText = "0 / 0";
        currentImageName.innerText = "Đã xóa hết ảnh trong bộ lọc";
      } else {
        if (currentIndex >= images.length) {
          currentIndex = images.length - 1;
        }
        await loadImageAndLabels(currentIndex);
      }
    } else {
      alert("Xóa ảnh không thành công!");
      deleteImageBtn.disabled = false;
    }
  } catch (err) {
    console.error("Error deleting image:", err);
    alert("Có lỗi xảy ra khi xóa ảnh!");
    deleteImageBtn.disabled = false;
  }
}

async function autoDeduplicateDataset() {
  const dataset = datasetSelect.value;
  if (!confirm(`Bạn có muốn tự động tìm và chuyển các bản sao augmented (trùng base) vào thư mục deleted không?`)) {
    return;
  }

  try {
    autoDedupBtn.disabled = true;
    autoDedupBtn.innerHTML = `<i class="fa-solid fa-spinner fa-spin mr-1"></i> Đang lọc...`;

    const res = await fetch(`/api/deduplicate/${dataset}`, { method: "POST" });
    const data = await res.json();

    if (res.ok) {
      alert(`Đã dọn dẹp thành công!\n- Chuyển vào deleted: ${data.moved} ảnh trùng lặp\n- Còn lại: ${data.kept} ảnh độc nhất.`);
      await loadImages();
    } else {
      alert("Lọc trùng lặp gặp lỗi!");
    }
  } catch (err) {
    console.error("Error deduplicating:", err);
    alert("Lỗi kết nối khi lọc trùng!");
  } finally {
    autoDedupBtn.disabled = false;
    autoDedupBtn.innerHTML = `<i class="fa-solid fa-broom mr-1"></i> Lọc trùng`;
  }
}
  }
}
