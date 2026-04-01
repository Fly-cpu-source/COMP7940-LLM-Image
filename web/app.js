(() => {
  const STATE_KEY = "autofigure_input_v2";

  const page = document.body.dataset.page;
  if (page === "input") {
    initInputPage();
  } else if (page === "canvas") {
    initCanvasPage();
  }

  function $(id) {
    return document.getElementById(id);
  }

  // -------------------------------------------------------------------------
  // Input page
  // -------------------------------------------------------------------------

  function initInputPage() {
    const confirmBtn = $("confirmBtn");
    const errorMsg = $("errorMsg");
    const uploadZone = $("uploadZone");
    const referenceFile = $("referenceFile");
    const referencePreview = $("referencePreview");
    const referenceStatus = $("referenceStatus");
    let uploadedReferencePath = null;

    function loadState() {
      try {
        const raw = window.sessionStorage.getItem(STATE_KEY);
        return raw ? JSON.parse(raw) : null;
      } catch (_) {
        return null;
      }
    }

    function saveState() {
      const state = {
        methodText: $("methodText")?.value ?? "",
        provider: $("provider")?.value ?? "gemini",
        apiKey: $("apiKey")?.value ?? "",
        referencePath: uploadedReferencePath,
        referenceUrl: referencePreview?.src ?? "",
        referenceStatus: referenceStatus?.textContent ?? "",
      };
      try {
        window.sessionStorage.setItem(STATE_KEY, JSON.stringify(state));
      } catch (_) {}
    }

    function applyState() {
      const s = loadState();
      if (!s) return;
      if (typeof s.methodText === "string") $("methodText").value = s.methodText;
      if (typeof s.provider === "string" && $("provider")) $("provider").value = s.provider;
      if (typeof s.apiKey === "string") $("apiKey").value = s.apiKey;
      if (typeof s.referencePath === "string") uploadedReferencePath = s.referencePath;
      if (referencePreview && typeof s.referenceUrl === "string" && s.referenceUrl) {
        referencePreview.src = s.referenceUrl;
        referencePreview.classList.add("visible");
      }
      if (referenceStatus && typeof s.referenceStatus === "string") {
        referenceStatus.textContent = s.referenceStatus;
      }
    }

    applyState();

    // Reference image upload
    if (uploadZone && referenceFile) {
      uploadZone.addEventListener("click", () => referenceFile.click());

      uploadZone.addEventListener("dragover", (e) => {
        e.preventDefault();
        uploadZone.classList.add("dragging");
      });
      uploadZone.addEventListener("dragleave", () => {
        uploadZone.classList.remove("dragging");
      });
      uploadZone.addEventListener("drop", async (e) => {
        e.preventDefault();
        uploadZone.classList.remove("dragging");
        const file = e.dataTransfer.files[0];
        if (file) {
          const result = await uploadReference(file, confirmBtn, referencePreview, referenceStatus);
          if (result) {
            uploadedReferencePath = result.path;
            saveState();
          }
        }
      });

      referenceFile.addEventListener("change", async () => {
        const file = referenceFile.files[0];
        if (file) {
          const result = await uploadReference(file, confirmBtn, referencePreview, referenceStatus);
          if (result) {
            uploadedReferencePath = result.path;
            saveState();
          }
        }
      });
    }

    // Auto-save on field changes
    for (const id of ["methodText", "provider", "apiKey"]) {
      const el = $(id);
      if (el) {
        el.addEventListener("input", saveState);
        el.addEventListener("change", saveState);
      }
    }

    // Submit
    confirmBtn.addEventListener("click", async () => {
      errorMsg.textContent = "";
      const methodText = $("methodText").value.trim();
      if (!methodText) {
        errorMsg.textContent = "Please provide method text.";
        return;
      }

      confirmBtn.disabled = true;
      confirmBtn.textContent = "Starting...";

      const payload = {
        method_text: methodText,
        provider: $("provider").value,
        api_key: $("apiKey").value.trim() || null,
        reference_image_path: uploadedReferencePath,
      };

      saveState();

      try {
        const resp = await fetch("/api/run", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });

        if (!resp.ok) {
          const text = await resp.text();
          throw new Error(text || "Request failed");
        }

        const data = await resp.json();
        window.location.href = `/canvas.html?job=${encodeURIComponent(data.job_id)}`;
      } catch (err) {
        errorMsg.textContent = err.message || "Failed to start job";
        confirmBtn.disabled = false;
        confirmBtn.textContent = "Generate Figure";
      }
    });
  }

  // -------------------------------------------------------------------------
  // Reference image upload helper
  // -------------------------------------------------------------------------

  async function uploadReference(file, confirmBtn, previewEl, statusEl) {
    if (!file.type.startsWith("image/")) {
      if (statusEl) statusEl.textContent = "Only image files are supported.";
      return null;
    }

    confirmBtn.disabled = true;
    if (statusEl) statusEl.textContent = "Uploading reference...";

    const form = new FormData();
    form.append("file", file);

    try {
      const resp = await fetch("/api/upload", { method: "POST", body: form });
      if (!resp.ok) {
        const text = await resp.text();
        throw new Error(text || "Upload failed");
      }
      const data = await resp.json();
      if (statusEl) statusEl.textContent = `Reference: ${data.name}`;
      if (previewEl) {
        previewEl.src = data.url || "";
        previewEl.classList.add("visible");
      }
      return { path: data.path || null, url: data.url || "", name: data.name || "" };
    } catch (err) {
      if (statusEl) statusEl.textContent = err.message || "Upload failed";
      return null;
    } finally {
      confirmBtn.disabled = false;
    }
  }

  // -------------------------------------------------------------------------
  // Canvas page
  // -------------------------------------------------------------------------

  function initCanvasPage() {
    const params = new URLSearchParams(window.location.search);
    const jobId = params.get("job");
    const statusText = $("statusText");
    const jobIdEl = $("jobId");
    const artifactPanel = $("artifactPanel");
    const artifactList = $("artifactList");
    const artifactToggle = $("artifactToggle");
    const logToggle = $("logToggle");
    const logPanel = $("logPanel");
    const logBody = $("logBody");
    const backBtn = $("backToConfigBtn");
    const figureImage = $("figureImage");

    if (!jobId) {
      statusText.textContent = "Missing job id";
      return;
    }

    jobIdEl.textContent = jobId;

    if (backBtn) {
      backBtn.addEventListener("click", () => { window.location.href = "/"; });
    }

    artifactToggle.addEventListener("click", () => {
      artifactPanel.classList.toggle("open");
    });

    logToggle.addEventListener("click", () => {
      logPanel.classList.toggle("open");
    });

    const seen = new Set();
    const src = new EventSource(`/api/events/${jobId}`);
    let finished = false;

    src.addEventListener("artifact", (e) => {
      const data = JSON.parse(e.data);
      if (!seen.has(data.path)) {
        seen.add(data.path);
        addArtifactCard(artifactList, data);
      }
      if (data.kind === "figure" && figureImage) {
        figureImage.src = data.url;
        figureImage.classList.add("visible");
        statusText.textContent = "Figure ready";
      }
    });

    src.addEventListener("status", (e) => {
      const data = JSON.parse(e.data);
      if (data.state === "started") {
        statusText.textContent = "Running...";
      } else if (data.state === "finished") {
        finished = true;
        statusText.textContent = data.code === 0 ? "Done" : `Failed (code ${data.code})`;
      }
    });

    src.addEventListener("log", (e) => {
      appendLog(logBody, JSON.parse(e.data));
    });

    src.onerror = () => {
      if (finished) { src.close(); return; }
      statusText.textContent = "Disconnected";
    };
  }

  // -------------------------------------------------------------------------
  // Shared helpers
  // -------------------------------------------------------------------------

  function appendLog(container, data) {
    const lines = container.textContent.split("\n").filter(Boolean);
    lines.push(`[${data.stream}] ${data.line}`);
    if (lines.length > 200) lines.splice(0, lines.length - 200);
    container.textContent = lines.join("\n");
    container.scrollTop = container.scrollHeight;
  }

  function addArtifactCard(container, data) {
    const card = document.createElement("a");
    card.className = "artifact-card";
    card.href = data.url;
    card.target = "_blank";
    card.rel = "noreferrer";

    const img = document.createElement("img");
    img.src = data.url;
    img.alt = data.name;
    img.loading = "lazy";

    const meta = document.createElement("div");
    meta.className = "artifact-meta";

    const nameEl = document.createElement("div");
    nameEl.className = "artifact-name";
    nameEl.textContent = data.name;

    const badge = document.createElement("div");
    badge.className = "artifact-badge";
    badge.textContent = data.kind === "figure" ? "figure" : "artifact";

    meta.appendChild(nameEl);
    meta.appendChild(badge);
    card.appendChild(img);
    card.appendChild(meta);
    container.prepend(card);
  }
})();
