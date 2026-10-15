/* ==========================================================================
   f2py Workbench — Frontend Application Controller
   ========================================================================== */
(function () {
  "use strict";

  const state = {
    activeView: "overview",
    theme: localStorage.getItem("f2py_theme") || "dark",
    tourStep: 0,
    kernels: [],
    selectedKernelId: "prodintent",
    kernelSearchQuery: "",
    kernelCategory: "all",
    history: [],
    precisionData: null,
    precisionMode: "aggregate",
    selectedTierId: "float64",
    presets: [],
    selectedPresetId: "badcomment_f77",
    pendingSheetPresetId: "badcomment_f77",
    presetSearchQuery: "",
    presetCategory: "all",
    cmapMode: "modern",
    lastSavedCode: "",
    lastFixedCode: "",
    isEditorDirty: false,
  };

  const TOUR_STEPS = [
    {
      stepLabel: "Step 1 of 3",
      title: "1. Understand Fortran INTENT Declarations in f2py",
      desc: "Unlike plain Fortran compilers where all subroutine parameters pass by mutable reference, f2py treats any parameter without an explicit INTENT as input-only (INTENT(IN)). Use INTENT(OUT) to return values to Python or INTENT(INOUT) with a numpy.ndarray buffer.",
      progress: "33.33%",
    },
    {
      stepLabel: "Step 2 of 3",
      title: "2. Map 64-Bit & 128-Bit Kinds in .f2py_f2cmap",
      desc: "By default, f2py maps Fortran real types to 32-bit C float. Always include a top-level .f2py_f2cmap mapping exact Fortran kind names (sp, dp, qp, real32, real64, real128) and use kind suffixes like 4.0_real64 * atan(1.0_real64).",
      progress: "66.66%",
    },
    {
      stepLabel: "Step 3 of 3",
      title: "3. Audit Fixed-Form (.f) vs Free-Form (.f90) Syntax",
      desc: "f2py strictly enforces Fortran 77 rules on .f files and rejects inline ! comments. Use the f2py Auditor tab to inspect and auto-remediate legacy .f and .f90 files before packaging.",
      progress: "100%",
    },
  ];

  // Utility: Escape HTML safely
  function escapeHtml(str) {
    return String(str ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  // Toast Notification (Area 9 & 10 — single active toast to prevent stacking)
  function showToast(message) {
    const container = document.getElementById("toast-container");
    if (!container) return;
    container.innerHTML = "";
    const item = document.createElement("div");
    item.className = "toast-item";
    item.innerHTML = `
      <svg viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <polyline points="20 6 9 17 4 12"></polyline>
      </svg>
      <span>${escapeHtml(message)}</span>
    `;
    container.appendChild(item);
    setTimeout(() => {
      if (item.parentNode) item.parentNode.removeChild(item);
    }, 2200);
  }

  // Theme Management (Area 6)
  function applyTheme(theme) {
    state.theme = theme === "light" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", state.theme);
    localStorage.setItem("f2py_theme", state.theme);
    document.querySelectorAll("[data-theme-choice]").forEach((btn) => {
      const active = btn.getAttribute("data-theme-choice") === state.theme;
      btn.classList.toggle("is-active", active);
      btn.setAttribute("aria-pressed", String(active));
    });
  }

  // Navigation Management (Desktop + Mobile Bottom Nav)
  function switchView(viewName, focusHeading = true) {
    const validViews = ["overview", "kernels", "precision", "auditor"];
    if (!validViews.includes(viewName)) return;
    state.activeView = viewName;

    validViews.forEach((v) => {
      const sec = document.getElementById(`view-${v}`);
      if (sec) {
        const isTarget = v === viewName;
        sec.hidden = !isTarget;
        sec.classList.toggle("is-active", isTarget);
      }
    });

    document.querySelectorAll("[data-nav-target]").forEach((btn) => {
      const isTarget = btn.getAttribute("data-nav-target") === viewName;
      btn.classList.toggle("is-active", isTarget);
      if (isTarget) {
        btn.setAttribute("aria-current", "page");
      } else {
        btn.removeAttribute("aria-current");
      }
    });

    if (focusHeading) {
      const heading = document.getElementById(`heading-${viewName}`);
      if (heading) {
        heading.focus({ preventScroll: true });
      }
    }

    if (viewName === "kernels") {
      requestAnimationFrame(updateTableScrollHint);
    }
  }

  // Conditional Horizontal Scroll Hint (Safeguard)
  function updateTableScrollHint() {
    const scroller = document.getElementById("comparison-table-scroller");
    const hint = document.getElementById("comparison-scroll-hint");
    if (!scroller || !hint) return;
    const overflows = scroller.scrollWidth > scroller.clientWidth + 4;
    hint.hidden = !overflows;
  }

  // Tour Banner Logic
  function renderTourStep() {
    const step = TOUR_STEPS[state.tourStep];
    if (!step) return;
    const ind = document.getElementById("tour-step-indicator");
    const title = document.getElementById("tour-step-title");
    const desc = document.getElementById("tour-step-desc");
    const bar = document.getElementById("tour-progress-bar");
    const prevBtn = document.getElementById("tour-prev-btn");
    const nextBtn = document.getElementById("tour-next-btn");

    if (ind) ind.textContent = step.stepLabel;
    if (title) title.textContent = step.title;
    if (desc) desc.textContent = step.desc;
    if (bar) bar.style.width = step.progress;
    if (prevBtn) prevBtn.disabled = state.tourStep === 0;
    if (nextBtn) {
      nextBtn.textContent = state.tourStep === TOUR_STEPS.length - 1 ? "Finish Tour" : "Next Step";
    }
  }

  // Render Routine Selector List
  function renderKernelSelector() {
    const listEl = document.getElementById("kernel-selector-list");
    const noResEl = document.getElementById("kernel-no-results");
    const noResText = document.getElementById("kernel-no-results-text");
    const countBadge = document.getElementById("kernel-filter-count");
    const clearBtn = document.getElementById("kernel-search-clear");

    if (!listEl) return;

    const q = state.kernelSearchQuery.trim().toLowerCase();
    if (clearBtn) clearBtn.hidden = q.length === 0;

    const filtered = state.kernels.filter((k) => {
      const catMatch = state.kernelCategory === "all" || k.category === state.kernelCategory;
      if (!catMatch) return false;
      if (!q) return true;
      const hay = `${k.name} ${k.fortran_name} ${k.intent_mode} ${k.precision} ${k.description}`.toLowerCase();
      return hay.includes(q);
    });

    if (countBadge) {
      countBadge.textContent = `${filtered.length} routine${filtered.length === 1 ? "" : "s"}`;
    }

    if (filtered.length === 0) {
      listEl.innerHTML = "";
      listEl.hidden = true;
      if (noResEl) noResEl.hidden = false;
      if (noResText) {
        noResText.textContent = `No Fortran routine matched "${state.kernelSearchQuery}" in the selected category.`;
      }
      return;
    }

    listEl.hidden = false;
    if (noResEl) noResEl.hidden = true;

    listEl.innerHTML = filtered
      .map((k) => {
        const isSelected = k.id === state.selectedKernelId;
        const badgeClass = `status-${k.status_type || "info"}`;
        return `
          <button
            type="button"
            class="kernel-option-card ${isSelected ? "is-selected" : ""}"
            role="option"
            aria-selected="${isSelected}"
            data-select-kernel="${escapeHtml(k.id)}"
          >
            <div class="option-top-line">
              <span class="option-name mono-text">${escapeHtml(k.name)}</span>
              <span class="status-badge ${badgeClass}">${escapeHtml(k.status_label)}</span>
            </div>
            <div class="option-desc">${escapeHtml(k.intent_mode)} • ${escapeHtml(k.precision)}</div>
          </button>
        `;
      })
      .join("");

    listEl.querySelectorAll("[data-select-kernel]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const kid = btn.getAttribute("data-select-kernel");
        selectKernel(kid, true);
      });
    });
  }

  function selectKernel(kernelId, autoRun = false) {
    state.selectedKernelId = kernelId;
    const meta = state.kernels.find((k) => k.id === kernelId);
    const subEl = document.getElementById("active-kernel-subtitle");
    const scalarGroup = document.getElementById("scalar-inputs-group");
    const vectorGroup = document.getElementById("vector-inputs-group");

    if (meta && subEl) {
      subEl.innerHTML = `Selected: <code>${escapeHtml(meta.signature)}</code>`;
    }
    if (meta && scalarGroup && vectorGroup) {
      const isVec = meta.category === "vector";
      scalarGroup.hidden = isVec;
      vectorGroup.hidden = !isVec;
    }

    renderKernelSelector();
    if (autoRun) {
      executeActiveKernel(false);
    }
  }

  function parseVectorInput(raw) {
    const parts = String(raw || "")
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
    if (parts.length === 0) {
      throw new Error("Please enter at least one comma-separated numeric value.");
    }
    const nums = parts.map((p) => {
      const n = Number(p);
      if (!Number.isFinite(n)) {
        throw new Error(`Invalid number "${p}" in vector input.`);
      }
      return n;
    });
    return nums;
  }

  async function executeActiveKernel(compareAll = false) {
    const alertBox = document.getElementById("kernel-validation-alert");
    const errTitle = document.getElementById("kernel-error-title");
    const errDesc = document.getElementById("kernel-error-desc");
    const errRec = document.getElementById("kernel-error-recovery");
    const submitBtn = document.getElementById("run-kernel-submit-btn");
    const submitLabel = document.getElementById("run-kernel-btn-label");

    if (alertBox) alertBox.hidden = true;
    if (errRec) errRec.hidden = true;

    const xVal = Number(document.getElementById("input-x")?.value ?? 3);
    const yVal = Number(document.getElementById("input-y")?.value ?? 2);
    const zInitVal = Number(document.getElementById("input-z-init")?.value ?? 12345.0);
    const useNdarray = Boolean(document.getElementById("input-use-ndarray")?.checked);

    let vecX = [1.5, 2.5, 3.5, 4.5];
    let vecY = [2.0, 4.0, 6.0, 8.0];

    try {
      if (!Number.isFinite(xVal) || !Number.isFinite(yVal) || !Number.isFinite(zInitVal)) {
        throw new Error("Scalar operands x, y, and initial z must be valid finite numbers.");
      }
      if (state.selectedKernelId === "prodinout" && !useNdarray) {
        if (alertBox && errTitle && errDesc) {
          errTitle.textContent = "f2py Type & Buffer Guard Triggered";
          errDesc.textContent =
            "Passing a plain Python float to an INTENT(INOUT) argument fails in f2py. Wrap the scalar in a 0-D NumPy array: np.array(23456.0).";
          alertBox.hidden = false;
          if (errRec) errRec.hidden = false;
        }
        return;
      }
      vecX = parseVectorInput(document.getElementById("input-vec-x")?.value);
      vecY = parseVectorInput(document.getElementById("input-vec-y")?.value);
      if (vecX.length !== vecY.length) {
        throw new Error(`Vector length mismatch: x has ${vecX.length} elements, y has ${vecY.length} elements.`);
      }
    } catch (validationErr) {
      if (alertBox && errTitle && errDesc) {
        errTitle.textContent = "Input Validation Error";
        errDesc.textContent = validationErr.message;
        alertBox.hidden = false;
      }
      return;
    }

    if (submitBtn) submitBtn.disabled = true;
    if (submitLabel) submitLabel.textContent = "Executing...";

    try {
      const resp = await fetch("/api/v1/compute/prod", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          kernel_id: state.selectedKernelId,
          x: xVal,
          y: yVal,
          z_init: zInitVal,
          use_ndarray_for_inout: useNdarray,
          vec_x: vecX,
          vec_y: vecY,
          compare_all: compareAll,
        }),
      });

      const data = await resp.json();
      if (!resp.ok) {
        const msg = data.detail || "Kernel execution failed.";
        if (alertBox && errTitle && errDesc) {
          errTitle.textContent = "f2py Type & Buffer Guard Triggered";
          errDesc.textContent = msg;
          alertBox.hidden = false;
          if (state.selectedKernelId === "prodinout" && !useNdarray && errRec) {
            errRec.hidden = false;
          }
        }
        return;
      }

      renderPrimaryTelemetry(data.primary);
      renderComparisonTable(data.comparison.results);
      await refreshHistory();
      showToast(`Executed ${data.primary.meta.name} in ${data.primary.latency_us} µs`);
    } catch (networkErr) {
      if (alertBox && errTitle && errDesc) {
        errTitle.textContent = "Service Communication Error";
        errDesc.textContent = networkErr.message;
        alertBox.hidden = false;
      }
    } finally {
      if (submitBtn) submitBtn.disabled = false;
      if (submitLabel) submitLabel.textContent = "Execute Fortran Kernel";
    }
  }

  function renderPrimaryTelemetry(primary) {
    if (!primary || !primary.meta) return;
    const meta = primary.meta;
    document.getElementById("res-fortran-sub").textContent = meta.fortran_name;
    document.getElementById("res-kernel-name").textContent = meta.name;

    const dispVal =
      primary.return_value !== null && primary.return_value !== undefined
        ? Array.isArray(primary.return_value)
          ? `[${primary.return_value.join(", ")}]`
          : String(primary.return_value)
        : `None (z=${primary.z_after})`;

    document.getElementById("res-primary-output").textContent = dispVal;
    document.getElementById("res-latency-badge").textContent = `${primary.latency_us} µs`;

    const statusBadge = document.getElementById("res-status-badge");
    if (statusBadge) {
      statusBadge.className = `status-badge status-${meta.status_type}`;
      statusBadge.textContent = meta.status_label;
    }

    document.getElementById("res-intent-chip").textContent = meta.intent_mode;
    document.getElementById("res-precision-chip").textContent = meta.precision;
    document.getElementById("res-explanation").textContent = primary.explanation;
    document.getElementById("res-fortran-code").textContent = meta.fortran_code;

    const pySnippet = buildPythonSnippet(primary);
    document.getElementById("res-python-call").textContent = pySnippet;
  }

  function buildPythonSnippet(primary) {
    const inp = primary.inputs || {};
    if (primary.kernel_id === "prodintent") {
      return `from pyprod import prod\nz = prod.prodintent(${inp.x}, ${inp.y})\nassert z == ${primary.return_value}  # returned via INTENT(OUT)`;
    }
    if (primary.kernel_id === "prodinout") {
      return `import numpy as np\nfrom pyprod import prod\nz = np.array(${inp.z_init}, dtype=np.float32)\nprod.prodinout(${inp.x}, ${inp.y}, z)\nassert float(z) == ${primary.z_after}  # mutated in-place`;
    }
    if (primary.kernel_id === "prodnointent") {
      return `from pyprod import prod\nz = ${inp.z_init}\nres = prod.prodnointent(${inp.x}, ${inp.y}, z)\nassert res is None and z == ${primary.z_after}  # unmodified!`;
    }
    if (primary.kernel_id === "prodpure") {
      return `from pyprod import prod\nz = prod.prodpure(${inp.x}, ${inp.y})\nassert z == ${primary.return_value}`;
    }
    if (primary.kernel_id === "prodvecintent") {
      return `import numpy as np\nfrom pyprod import prod\nx = np.array(${JSON.stringify(inp.vec_x)}, dtype=np.float64)\ny = np.array(${JSON.stringify(inp.vec_y)}, dtype=np.float64)\nz = prod.prodvecintent(x, y)\n# z => ${JSON.stringify(primary.return_value)}`;
    }
    return `import numpy as np\nfrom pyprod import prod\ndot_val = prod.proddotdp(${JSON.stringify(inp.vec_x)}, ${JSON.stringify(inp.vec_y)})\nassert dot_val == ${primary.return_value}`;
  }

  function renderComparisonTable(results) {
    const tbody = document.getElementById("intent-comparison-tbody");
    if (!tbody || !Array.isArray(results)) return;
    tbody.innerHTML = results
      .map((r) => {
        const retText =
          r.return_value === null
            ? "None"
            : Array.isArray(r.return_value)
              ? `[${r.return_value.join(", ")}]`
              : String(r.return_value);
        const zAfterText = Array.isArray(r.z_after) ? `[${r.z_after.join(", ")}]` : String(r.z_after);
        return `
          <tr>
            <td class="mono-text"><strong>${escapeHtml(r.meta.name)}</strong></td>
            <td>${escapeHtml(r.meta.intent_mode)}</td>
            <td class="mono-text">${escapeHtml(retText)}</td>
            <td class="mono-text">${escapeHtml(zAfterText)}</td>
            <td><span class="status-badge status-${escapeHtml(r.meta.status_type)}">${escapeHtml(r.meta.status_label)}</span></td>
            <td class="mono-text">${escapeHtml(r.latency_us)} µs</td>
          </tr>
        `;
      })
      .join("");
    requestAnimationFrame(updateTableScrollHint);
  }

  // Session Run History (Overview Tab: First-Use Empty State + Populated List)
  async function refreshHistory() {
    try {
      const resp = await fetch("/api/v1/history");
      const data = await resp.json();
      state.history = data.runs || [];
      renderHistoryList();
    } catch (_err) {
      // Keep existing state if offline
    }
  }

  function renderHistoryList() {
    const emptyBox = document.getElementById("history-empty-state");
    const listWrap = document.getElementById("history-list-wrapper");
    const countBadge = document.getElementById("history-count-badge");
    const clearBtn = document.getElementById("clear-history-btn");

    const count = state.history.length;
    if (countBadge) {
      countBadge.textContent = `${count} run${count === 1 ? "" : "s"}`;
    }
    if (clearBtn) {
      clearBtn.hidden = count === 0;
    }

    if (count === 0) {
      if (emptyBox) emptyBox.hidden = false;
      if (listWrap) {
        listWrap.hidden = true;
        listWrap.innerHTML = "";
      }
      return;
    }

    if (emptyBox) emptyBox.hidden = true;
    if (listWrap) {
      listWrap.hidden = false;
      listWrap.innerHTML = state.history
        .map((item) => {
          const outStr = Array.isArray(item.output) ? `[${item.output.join(", ")}]` : String(item.output);
          return `
            <div class="record-row" role="listitem">
              <div class="record-main">
                <div class="record-title-line">
                  <span class="record-title mono-text">${escapeHtml(item.kernel_name)}</span>
                  <span class="status-badge status-${escapeHtml(item.status_type)}">${escapeHtml(item.status_label)}</span>
                </div>
                <div class="record-meta">
                  ${escapeHtml(item.intent_mode)} • Run ID <code>${escapeHtml(item.run_id)}</code> • ${escapeHtml(item.timestamp)}
                </div>
              </div>
              <div class="record-right">
                <span class="record-output-val mono-text">Out: ${escapeHtml(outStr)}</span>
                <span class="meta-chip mono-text">${escapeHtml(item.latency_us)} µs</span>
                <button
                  type="button"
                  class="icon-close-btn"
                  data-delete-run="${escapeHtml(item.run_id)}"
                  aria-label="Remove calculation run ${escapeHtml(item.run_id)} from log"
                  title="Remove run"
                >
                  <svg viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" stroke-width="1.75" fill="none" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                    <line x1="18" y1="6" x2="6" y2="18"></line>
                    <line x1="6" y1="6" x2="18" y2="18"></line>
                  </svg>
                </button>
              </div>
            </div>
          `;
        })
        .join("");

      listWrap.querySelectorAll("[data-delete-run]").forEach((btn) => {
        btn.addEventListener("click", async () => {
          const rid = btn.getAttribute("data-delete-run");
          await fetch(`/api/v1/history/${encodeURIComponent(rid)}`, { method: "DELETE" });
          await refreshHistory();
          showToast(`Removed run ${rid}`);
        });
      });
    }
  }

  // Precision Explorer Rendering
  async function loadPrecisionData() {
    try {
      const resp = await fetch("/api/v1/precision/ieee754");
      state.precisionData = await resp.json();
      renderPrecisionExplorer();
    } catch (_err) {
      // ignore
    }
  }

  function renderPrecisionExplorer() {
    if (!state.precisionData) return;
    const { tiers, cmap_comparison } = state.precisionData;

    const barsContainer = document.getElementById("precision-bars-container");
    if (barsContainer && Array.isArray(tiers)) {
      barsContainer.innerHTML = tiers
        .map((t) => {
          const widthPct = Math.min(100, Math.round((t.mantissa_bits / 128) * 100));
          return `
            <div class="chart-row">
              <div class="chart-row-label">
                <span class="chart-tier-title">${escapeHtml(t.label)}</span>
                <span class="chart-tier-sub mono-text">${escapeHtml(t.fortran_kind)}</span>
              </div>
              <div class="chart-bar-track">
                <div class="chart-bar-fill" style="width: ${widthPct}%"></div>
                <span class="chart-bar-value">${escapeHtml(t.mantissa_bits)} bits (~${escapeHtml(t.decimal_digits)} dec digits)</span>
              </div>
              <div class="chart-epsilon-cell mono-text">ε = ${escapeHtml(t.machine_epsilon)}</div>
            </div>
          `;
        })
        .join("");
    }

    renderIndividualTierDetail();

    const cmapGrid = document.getElementById("cmap-cases-grid");
    if (cmapGrid && cmap_comparison && Array.isArray(cmap_comparison.cases)) {
      cmapGrid.innerHTML = cmap_comparison.cases
        .map((c) => {
          return `
            <article class="surface-card capability-card">
              <div class="card-top-row">
                <h3 class="card-title">${escapeHtml(c.title)}</h3>
                <span class="status-badge status-${escapeHtml(c.status)}">${escapeHtml(c.status_label)}</span>
              </div>
              <div class="code-preview-box mono-text">
                <div>${escapeHtml(c.fortran_decl)}</div>
                <div class="code-comment"># .f2py_f2cmap: ${escapeHtml(c.cmap_entry)}</div>
              </div>
              <dl class="runtime-kv-list">
                <div class="runtime-kv-row">
                  <dt>Resolved C Type</dt>
                  <dd class="mono-text">${escapeHtml(c.resolved_c_type)}</dd>
                </div>
                <div class="runtime-kv-row">
                  <dt>Evaluated π Value</dt>
                  <dd class="mono-text">${escapeHtml(c.value_str)}</dd>
                </div>
                <div class="runtime-kv-row">
                  <dt>Absolute Error |π - val|</dt>
                  <dd class="mono-text">${escapeHtml(c.abs_error)} (${escapeHtml(c.accurate_digits)} digits)</dd>
                </div>
              </dl>
            </article>
          `;
        })
        .join("");
    }
  }

  function renderIndividualTierDetail() {
    if (!state.precisionData) return;
    const panel = document.getElementById("individual-tier-panel");
    const grid = document.getElementById("individual-tier-detail");
    if (!panel || !grid) return;

    panel.hidden = state.precisionMode !== "individual";
    const tier = state.precisionData.tiers.find((t) => t.id === state.selectedTierId) || state.precisionData.tiers[2];
    if (!tier) return;

    grid.innerHTML = `
      <div class="tier-stat-box">
        <span class="tier-stat-label">Fortran Kind Specifier</span>
        <span class="tier-stat-val mono-text">${escapeHtml(tier.fortran_kind)}</span>
      </div>
      <div class="tier-stat-box">
        <span class="tier-stat-label">NumPy Equivalent Dtype</span>
        <span class="tier-stat-val mono-text">${escapeHtml(tier.numpy_dtype)}</span>
      </div>
      <div class="tier-stat-box">
        <span class="tier-stat-label">Significand / Total Bits</span>
        <span class="tier-stat-val mono-text">${escapeHtml(tier.mantissa_bits)} / ${escapeHtml(tier.total_bits)} bits</span>
      </div>
      <div class="tier-stat-box">
        <span class="tier-stat-label">Decimal Precision &amp; π Error</span>
        <span class="tier-stat-val mono-text">${escapeHtml(tier.decimal_digits)} digits (err: ${escapeHtml(tier.pi_error)})</span>
      </div>
    `;
  }

  // Auditor & Bottom Sheet Presets
  async function loadPresets() {
    try {
      const resp = await fetch("/api/v1/presets");
      const data = await resp.json();
      state.presets = data.presets || [];
      if (state.presets.length > 0) {
        applyPresetById(state.presets[0].id, false);
      }
      renderPresetSheetList();
    } catch (_err) {
      // ignore
    }
  }

  function applyPresetById(presetId, notify = true) {
    const preset = state.presets.find((p) => p.id === presetId);
    if (!preset) return;
    state.selectedPresetId = preset.id;
    state.pendingSheetPresetId = preset.id;
    state.lastSavedCode = preset.code;
    state.isEditorDirty = false;

    const fnInput = document.getElementById("audit-filename-input");
    const codeArea = document.getElementById("audit-code-textarea");
    const fileLabel = document.getElementById("auditor-active-file-label");
    const ctxBar = document.getElementById("auditor-contextual-bar");

    if (fnInput) fnInput.value = preset.filename;
    if (codeArea) codeArea.value = preset.code;
    if (fileLabel) fileLabel.innerHTML = `Active file: <code>${escapeHtml(preset.filename)}</code>`;
    if (ctxBar) ctxBar.hidden = true;

    runFortranAudit(false);
    if (notify) {
      showToast(`Loaded preset ${preset.filename}`);
    }
  }

  async function runFortranAudit(showNotification = true) {
    const fnInput = document.getElementById("audit-filename-input");
    const codeArea = document.getElementById("audit-code-textarea");
    if (!fnInput || !codeArea) return;

    const filename = fnInput.value.trim() || "snippet.f90";
    const code = codeArea.value;

    try {
      const resp = await fetch("/api/v1/diagnostics/audit", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          code,
          filename,
          cmap_mode: state.cmapMode,
        }),
      });
      const res = await resp.json();
      state.lastFixedCode = res.fixed_code || code;
      renderAuditFindings(res);
      if (showNotification) {
        showToast(`Audit completed: ${res.overall_label}`);
      }
    } catch (_err) {
      // ignore
    }
  }

  function renderAuditFindings(res) {
    const badge = document.getElementById("auditor-overall-badge");
    const dialectChip = document.getElementById("auditor-dialect-chip");
    const listEl = document.getElementById("audit-findings-list");
    const cmapEl = document.getElementById("audit-recommended-cmap");
    const pyiEl = document.getElementById("audit-generated-pyi");
    const fileLabel = document.getElementById("auditor-active-file-label");

    if (fileLabel) {
      fileLabel.innerHTML = `Active file: <code>${escapeHtml(res.filename)}</code>`;
    }
    if (badge) {
      badge.className = `status-badge status-${res.overall_status}`;
      badge.textContent = res.overall_label;
    }
    if (dialectChip) {
      dialectChip.textContent = res.dialect;
    }
    if (cmapEl) {
      cmapEl.textContent = res.recommended_cmap;
    }
    if (pyiEl && res.generated_pyi_stub) {
      pyiEl.textContent = res.generated_pyi_stub.trim();
    }
    if (!listEl) return;

    if (!res.findings || res.findings.length === 0) {
      listEl.innerHTML = `
        <div class="finding-item">
          <div class="finding-top">
            <span class="finding-title">Zero f2py Compatibility Issues Found</span>
            <span class="status-badge status-success">Passed All Checks</span>
          </div>
          <p class="finding-msg">
            This Fortran source file includes <code>implicit none</code>, adheres to comment rules for ${escapeHtml(res.dialect)}, and maps all floating-point kinds cleanly.
          </p>
        </div>
      `;
      return;
    }

    listEl.innerHTML = res.findings
      .map((f) => {
        return `
          <div class="finding-item">
            <div class="finding-top">
              <span class="finding-title">Line ${escapeHtml(f.line)}: ${escapeHtml(f.title)}</span>
              <span class="status-badge status-${escapeHtml(f.severity)}">${escapeHtml(f.rule_id)}</span>
            </div>
            <p class="finding-msg">${escapeHtml(f.message)}</p>
            <div class="finding-fix"><strong>Fix:</strong> ${escapeHtml(f.suggestion)}</div>
          </div>
        `;
      })
      .join("");
  }

  // 1D Heat Diffusion PDE Simulation & Benchmark Lab (Phase 7)
  let activePdePulse = "gaussian";
  let activeBenchWorkload = "dot_product";

  async function runPdeSimulation(notify = false) {
    const stepsInput = document.getElementById("pde-steps-input");
    const alphaInput = document.getElementById("pde-alpha-input");
    const steps = Math.max(1, Math.min(250, Number(stepsInput?.value || 35)));
    const alpha = Math.max(0.0005, Math.min(0.05, Number(alphaInput?.value || 0.01)));

    try {
      const resp = await fetch("/api/v1/pde/simulate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          n: 41,
          steps,
          alpha,
          pulse_type: activePdePulse,
        }),
      });
      if (!resp.ok) return;
      const data = await resp.json();
      renderPdeChart(data);
      if (notify) {
        showToast(`Simulated ${data.steps} PDE steps (CFL r=${data.cfl_number})`);
      }
    } catch (_err) {
      // ignore
    }
  }

  function renderPdeChart(data) {
    const badge = document.getElementById("pde-cfl-badge");
    const energyEl = document.getElementById("pde-energy-readout");
    const quadNote = document.getElementById("pde-quadratic-note");
    const svg = document.getElementById("pde-svg-chart");

    if (badge) {
      badge.className = `status-badge ${data.is_stable ? "status-success" : "status-danger"}`;
      badge.textContent = `${data.stability_label} (r = ${data.cfl_number})`;
    }
    if (energyEl) {
      energyEl.textContent = `Peak Retention: ${data.peak_retention_pct}%`;
    }
    if (quadNote && data.quadratic_stability) {
      quadNote.textContent = `Citardauq Δ = ${Number(data.quadratic_stability.cancellation_error).toExponential(2)}`;
    }
    if (!svg || !Array.isArray(data.u_init) || !Array.isArray(data.u_final)) return;

    const w = 420;
    const h = 140;
    const padX = 14;
    const padY = 14;
    const maxVal = Math.max(1.0, ...data.u_init, ...data.u_final.map((v) => Math.min(2.5, Math.abs(v))));
    const n = data.u_init.length;

    const toPts = (arr) =>
      arr
        .map((v, i) => {
          const clamped = Math.max(-0.2, Math.min(2.0, v));
          const x = padX + (i / Math.max(1, n - 1)) * (w - 2 * padX);
          const y = h - padY - (clamped / maxVal) * (h - 2 * padY);
          return `${x.toFixed(1)},${y.toFixed(1)}`;
        })
        .join(" ");

    const initPts = toPts(data.u_init);
    const finalPts = toPts(data.u_final);

    svg.innerHTML = `
      <line x1="${padX}" y1="${h - padY}" x2="${w - padX}" y2="${h - padY}" stroke="currentColor" stroke-opacity="0.18" stroke-width="1" />
      <polyline fill="none" stroke="#94A3B8" stroke-width="1.75" stroke-dasharray="4 4" points="${initPts}" />
      <polyline fill="none" stroke="#6366F1" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" points="${finalPts}" />
    `;
  }

  async function runLiveBenchmark(notify = false) {
    try {
      const resp = await fetch("/api/v1/benchmarks/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          workload: activeBenchWorkload,
          size: 5000,
          iterations: 20,
        }),
      });
      if (!resp.ok) return;
      const data = await resp.json();
      renderBenchmarkChart(data);
      if (notify) {
        showToast(`Benchmark complete: ${data.speedup_vs_python}x faster than Python loop`);
      }
    } catch (_err) {
      // ignore
    }
  }

  function renderBenchmarkChart(data) {
    const routineEl = document.getElementById("bench-routine-label");
    const speedupBadge = document.getElementById("bench-speedup-badge");
    const accNote = document.getElementById("bench-accuracy-note");
    const barsEl = document.getElementById("bench-bars-container");

    if (routineEl) {
      routineEl.innerHTML = `<code>${escapeHtml(data.fortran_routine)}</code> (N=${escapeHtml(data.size)})`;
    }
    if (speedupBadge) {
      speedupBadge.textContent = `${data.speedup_vs_python}x Faster`;
    }
    if (accNote) {
      accNote.textContent = data.result_summary;
    }
    if (!barsEl || !Array.isArray(data.series)) return;

    const maxLatency = Math.max(1, ...data.series.map((s) => s.latency_us));
    barsEl.innerHTML = data.series
      .map((s) => {
        const widthPct = Math.max(8, Math.min(100, Math.round((s.latency_us / maxLatency) * 100)));
        const toneClass = s.tone === "success" ? "tone-success" : s.tone === "warning" ? "tone-warning" : "";
        return `
          <div class="chart-row">
            <div class="chart-row-label">
              <span class="chart-tier-title">${escapeHtml(s.label)}</span>
              <span class="chart-tier-sub mono-text">${escapeHtml(s.relative_speedup)}</span>
            </div>
            <div class="chart-bar-track">
              <div class="chart-bar-fill ${toneClass}" style="width: ${widthPct}%"></div>
              <span class="chart-bar-value">${escapeHtml(s.latency_us)} µs</span>
            </div>
            <div class="chart-epsilon-cell mono-text">${escapeHtml(s.relative_speedup)}</div>
          </div>
        `;
      })
      .join("");
  }

  async function exportDiagnosticReport() {
    try {
      const resp = await fetch("/api/v1/export/report");
      if (!resp.ok) return;
      const report = await resp.json();
      const blob = new Blob([JSON.stringify(report, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "f2py-diagnostic-report.json";
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      showToast("Exported f2py-diagnostic-report.json");
    } catch (_err) {
      showToast("Failed to export report");
    }
  }

  // Phase 9: Column-Major Matrix & Simpson 1/3 Quadrature Explorer
  let activeMatrixPreset = "rotation_scale";
  let activeMatrixOrder = "F";
  let activeQuadFunc = "sin_pi";

  async function runNumericsExplorer(notify = false) {
    const ptsInput = document.getElementById("quad-points-input");
    const points = Math.max(11, Math.min(501, Number(ptsInput?.value || 101)));

    try {
      const resp = await fetch("/api/v1/numerics/explore", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          matrix_preset: activeMatrixPreset,
          order_mode: activeMatrixOrder,
          integrand: activeQuadFunc,
          points,
        }),
      });
      if (!resp.ok) return;
      const data = await resp.json();
      renderNumericsExplorer(data);
      if (notify) {
        showToast(`Evaluated ${data.matrix.title} & ${data.quadrature.label}`);
      }
    } catch (_err) {
      // ignore
    }
  }

  function renderNumericsExplorer(data) {
    if (!data || !data.matrix || !data.quadrature) return;
    const { matrix, quadrature } = data;

    const matSub = document.getElementById("mat-preset-subtitle");
    const matBadge = document.getElementById("mat-abi-badge");
    const matStrides = document.getElementById("mat-strides-val");
    const matCond = document.getElementById("mat-cond-val");
    const matErr = document.getElementById("mat-blas-err");
    const matPre = document.getElementById("mat-output-pre");

    if (matSub) matSub.textContent = matrix.title;
    if (matBadge) {
      matBadge.className = `status-badge ${matrix.f_contiguous ? "status-success" : "status-warning"}`;
      matBadge.textContent = matrix.f_contiguous ? "Zero-Copy (order='F')" : "Implicit Copy (order='C')";
    }
    if (matStrides) {
      matStrides.textContent = `(${matrix.strides_bytes.join(", ")}) bytes • F_CONTIGUOUS=${matrix.f_contiguous}`;
    }
    if (matCond) {
      matCond.textContent = `κ=${matrix.condition_number_a} • ||C||=${matrix.frobenius_norm_c} • det(C)=${matrix.determinant_c}`;
    }
    if (matErr) {
      matErr.textContent = `max |F90 − BLAS| = ${Number(matrix.max_abs_err_vs_blas).toExponential(1)}`;
    }
    if (matPre && Array.isArray(matrix.matrix_c)) {
      const formattedRows = matrix.matrix_c.map(
        (row) => `  [ ${row.map((v) => v.toFixed(5).padStart(9, " ")).join(", ")} ]`
      );
      matPre.textContent = `[\n${formattedRows.join(",\n")}\n]`;
    }

    const quadSub = document.getElementById("quad-func-subtitle");
    const quadBadge = document.getElementById("quad-gain-badge");
    const quadDx = document.getElementById("quad-dx-display");
    const quadExact = document.getElementById("quad-exact-val");
    const quadSimp = document.getElementById("quad-simpson-val");
    const quadTrap = document.getElementById("quad-trapz-val");

    if (quadSub) {
      quadSub.textContent = `${quadrature.label} (N=${quadrature.points} nodes)`;
    }
    if (quadBadge) {
      quadBadge.textContent = `${quadrature.accuracy_gain_x}x More Accurate`;
    }
    if (quadDx) {
      quadDx.textContent = String(quadrature.dx);
    }
    if (quadExact) {
      quadExact.textContent = Number(quadrature.exact_value).toFixed(15);
    }
    if (quadSimp) {
      quadSimp.textContent = `${Number(quadrature.simpson_value).toFixed(15)} (|err| = ${Number(quadrature.simpson_abs_error).toExponential(2)})`;
    }
    if (quadTrap) {
      quadTrap.textContent = `${Number(quadrature.trapezoid_value).toFixed(15)} (|err| = ${Number(quadrature.trapezoid_abs_error).toExponential(2)})`;
    }
  }

  // Bottom Sheet Modal Logic (Mobile #5 & #6)
  function openPresetSheet() {
    const backdrop = document.getElementById("preset-sheet-backdrop");
    if (!backdrop) return;
    state.pendingSheetPresetId = state.selectedPresetId;
    renderPresetSheetList();
    backdrop.hidden = false;
    const closeBtn = document.getElementById("close-preset-sheet-btn");
    if (closeBtn) closeBtn.focus();
  }

  function closePresetSheet(restoreFocus = true) {
    const backdrop = document.getElementById("preset-sheet-backdrop");
    if (!backdrop) return;
    backdrop.hidden = true;
    if (restoreFocus) {
      const trigger = document.getElementById("open-preset-sheet-btn");
      if (trigger) trigger.focus();
    }
  }

  function renderPresetSheetList() {
    const listEl = document.getElementById("preset-options-list");
    const noResEl = document.getElementById("preset-no-results");
    const noResMsg = document.getElementById("preset-no-results-msg");
    const clearBtn = document.getElementById("preset-search-clear");
    if (!listEl) return;

    const q = state.presetSearchQuery.trim().toLowerCase();
    if (clearBtn) clearBtn.hidden = q.length === 0;

    const filtered = state.presets.filter((p) => {
      const catOk = state.presetCategory === "all" || p.category === state.presetCategory;
      if (!catOk) return false;
      if (!q) return true;
      return `${p.filename} ${p.title} ${p.summary} ${p.category}`.toLowerCase().includes(q);
    });

    if (filtered.length === 0) {
      listEl.innerHTML = "";
      listEl.hidden = true;
      if (noResEl) noResEl.hidden = false;
      if (noResMsg) {
        noResMsg.textContent = `No Fortran preset matched "${state.presetSearchQuery}".`;
      }
      return;
    }

    listEl.hidden = false;
    if (noResEl) noResEl.hidden = true;

    listEl.innerHTML = filtered
      .map((p) => {
        const isSel = p.id === state.pendingSheetPresetId;
        return `
          <button
            type="button"
            class="preset-option-card ${isSel ? "is-selected" : ""}"
            role="option"
            aria-selected="${isSel}"
            data-sheet-preset="${escapeHtml(p.id)}"
          >
            <div class="option-top-line">
              <span class="option-name">${escapeHtml(p.title)}</span>
              <span class="meta-chip mono-text">${escapeHtml(p.filename)}</span>
            </div>
            <div class="option-desc">${escapeHtml(p.summary)}</div>
          </button>
        `;
      })
      .join("");

    listEl.querySelectorAll("[data-sheet-preset]").forEach((btn) => {
      btn.addEventListener("click", () => {
        state.pendingSheetPresetId = btn.getAttribute("data-sheet-preset");
        renderPresetSheetList();
      });
    });
  }

  // Copy to Clipboard Micro-Interaction (Area 10)
  function bindCopyButtons() {
    document.querySelectorAll("[data-copy-target]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const targetId = btn.getAttribute("data-copy-target");
        const targetEl = document.getElementById(targetId);
        if (!targetEl) return;
        const text = "value" in targetEl ? targetEl.value : targetEl.textContent;
        try {
          await navigator.clipboard.writeText(text || "");
        } catch (_err) {
          // Fallback copy
        }
        const labelSpan = btn.querySelector(".copy-btn-text");
        const origText = labelSpan ? labelSpan.textContent : "Copy";
        btn.classList.add("is-copied");
        if (labelSpan) labelSpan.textContent = "Copied!";
        showToast("Copied to clipboard");
        setTimeout(() => {
          btn.classList.remove("is-copied");
          if (labelSpan) labelSpan.textContent = origText;
        }, 1600);
      });
    });
  }

  // Initialize Event Listeners & Fetch Initial Data
  async function init() {
    applyTheme(state.theme);

    // Root input-modality tracker for shared focus policy
    document.addEventListener("keydown", (e) => {
      if (e.key === "Tab" || e.key.startsWith("Arrow")) {
        document.documentElement.classList.add("is-keyboard-nav");
      }
    });
    document.addEventListener("pointerdown", () => {
      document.documentElement.classList.remove("is-keyboard-nav");
    });

    // Theme buttons
    document.querySelectorAll("[data-theme-choice]").forEach((btn) => {
      btn.addEventListener("click", () => {
        applyTheme(btn.getAttribute("data-theme-choice"));
      });
    });

    // Navigation buttons
    document.querySelectorAll("[data-nav-target]").forEach((btn) => {
      btn.addEventListener("click", () => {
        switchView(btn.getAttribute("data-nav-target"), true);
      });
    });

    // Jump view buttons
    document.querySelectorAll("[data-jump-view]").forEach((btn) => {
      btn.addEventListener("click", () => {
        switchView(btn.getAttribute("data-jump-view"), true);
      });
    });

    // Runtime Popover
    const rtBtn = document.getElementById("runtime-menu-btn");
    const rtPopover = document.getElementById("runtime-popover");
    const closeRtBtn = document.getElementById("close-runtime-popover");
    if (rtBtn && rtPopover) {
      rtBtn.addEventListener("click", () => {
        const isOpen = !rtPopover.hidden;
        rtPopover.hidden = isOpen;
        rtBtn.setAttribute("aria-expanded", String(!isOpen));
      });
      if (closeRtBtn) {
        closeRtBtn.addEventListener("click", () => {
          rtPopover.hidden = true;
          rtBtn.setAttribute("aria-expanded", "false");
          rtBtn.focus();
        });
      }
      document.addEventListener("click", (e) => {
        if (!rtPopover.hidden && !rtPopover.contains(e.target) && !rtBtn.contains(e.target)) {
          rtPopover.hidden = true;
          rtBtn.setAttribute("aria-expanded", "false");
        }
      });
    }

    const copyCmapPopoverBtn = document.getElementById("copy-cmap-popover-btn");
    if (copyCmapPopoverBtn) {
      copyCmapPopoverBtn.addEventListener("click", async () => {
        const cmapStr =
          "dict(real=dict(sp='float', dp='double', qp='long_double', real32='float', real64='double', real128='long_double'))";
        try {
          await navigator.clipboard.writeText(cmapStr);
        } catch (_e) {}
        showToast("Copied production .f2py_f2cmap to clipboard");
      });
    }

    // Onboarding Tour Controls
    renderTourStep();
    document.getElementById("tour-prev-btn")?.addEventListener("click", () => {
      if (state.tourStep > 0) {
        state.tourStep -= 1;
        renderTourStep();
      }
    });
    document.getElementById("tour-next-btn")?.addEventListener("click", () => {
      if (state.tourStep < TOUR_STEPS.length - 1) {
        state.tourStep += 1;
        renderTourStep();
      } else {
        const banner = document.getElementById("onboarding-banner");
        if (banner) banner.hidden = true;
      }
    });
    document.getElementById("tour-skip-btn")?.addEventListener("click", () => {
      const banner = document.getElementById("onboarding-banner");
      if (banner) banner.hidden = true;
    });

    // First-Use Empty State CTA
    document.getElementById("run-first-kernel-btn")?.addEventListener("click", async () => {
      await executeActiveKernel(false);
    });
    document.getElementById("clear-history-btn")?.addEventListener("click", async () => {
      await fetch("/api/v1/history", { method: "DELETE" });
      await refreshHistory();
      showToast("Cleared session calculation log");
    });

    // Kernel Search & Category Filter
    const kSearch = document.getElementById("kernel-search-input");
    if (kSearch) {
      kSearch.addEventListener("input", () => {
        state.kernelSearchQuery = kSearch.value;
        renderKernelSelector();
      });
    }
    document.getElementById("kernel-search-clear")?.addEventListener("click", () => {
      state.kernelSearchQuery = "";
      if (kSearch) {
        kSearch.value = "";
        kSearch.focus();
      }
      renderKernelSelector();
    });
    document.getElementById("reset-kernel-search-btn")?.addEventListener("click", () => {
      state.kernelSearchQuery = "";
      state.kernelCategory = "all";
      if (kSearch) kSearch.value = "";
      document.querySelectorAll("[data-kernel-cat]").forEach((c) => {
        const isAll = c.getAttribute("data-kernel-cat") === "all";
        c.classList.toggle("is-active", isAll);
        c.setAttribute("aria-pressed", String(isAll));
      });
      renderKernelSelector();
    });
    document.querySelectorAll("[data-suggest-kernel]").forEach((chip) => {
      chip.addEventListener("click", () => {
        const kw = chip.getAttribute("data-suggest-kernel") || "";
        state.kernelSearchQuery = kw;
        state.kernelCategory = "all";
        if (kSearch) kSearch.value = kw;
        renderKernelSelector();
      });
    });
    document.querySelectorAll("[data-kernel-cat]").forEach((chip) => {
      chip.addEventListener("click", () => {
        state.kernelCategory = chip.getAttribute("data-kernel-cat") || "all";
        document.querySelectorAll("[data-kernel-cat]").forEach((c) => {
          const active = c === chip;
          c.classList.toggle("is-active", active);
          c.setAttribute("aria-pressed", String(active));
        });
        renderKernelSelector();
      });
    });

    // Progressive Disclosure in Kernel Form
    const advBtn = document.getElementById("toggle-advanced-buffer-btn");
    const advContent = document.getElementById("advanced-buffer-fields");
    if (advBtn && advContent) {
      advBtn.addEventListener("click", () => {
        const expanded = advBtn.getAttribute("aria-expanded") === "true";
        advBtn.setAttribute("aria-expanded", String(!expanded));
        advContent.hidden = expanded;
      });
    }

    // Kernel Form Execution & Error Recovery
    document.getElementById("kernel-exec-form")?.addEventListener("submit", (e) => {
      e.preventDefault();
      executeActiveKernel(false);
    });
    document.getElementById("compare-all-kernels-btn")?.addEventListener("click", () => {
      executeActiveKernel(true);
    });
    document.getElementById("reset-kernel-inputs-btn")?.addEventListener("click", () => {
      document.getElementById("input-x").value = "3";
      document.getElementById("input-y").value = "2";
      document.getElementById("input-z-init").value = "12345.0";
      document.getElementById("input-use-ndarray").checked = true;
      document.getElementById("input-vec-x").value = "1.5, 2.5, 3.5, 4.5";
      document.getElementById("input-vec-y").value = "2.0, 4.0, 6.0, 8.0";
      document.getElementById("kernel-validation-alert").hidden = true;
      executeActiveKernel(false);
    });
    document.getElementById("fix-ndarray-error-btn")?.addEventListener("click", () => {
      const cb = document.getElementById("input-use-ndarray");
      if (cb) cb.checked = true;
      executeActiveKernel(false);
    });

    // Precision Mode Toggle
    document.querySelectorAll("[data-prec-mode]").forEach((btn) => {
      btn.addEventListener("click", () => {
        state.precisionMode = btn.getAttribute("data-prec-mode") || "aggregate";
        document.querySelectorAll("[data-prec-mode]").forEach((b) => {
          const active = b === btn;
          b.classList.toggle("is-active", active);
          b.setAttribute("aria-pressed", String(active));
        });
        renderIndividualTierDetail();
      });
    });
    document.querySelectorAll("[data-tier-id]").forEach((btn) => {
      btn.addEventListener("click", () => {
        state.selectedTierId = btn.getAttribute("data-tier-id") || "float64";
        document.querySelectorAll("[data-tier-id]").forEach((b) => {
          const active = b === btn;
          b.classList.toggle("is-active", active);
          b.setAttribute("aria-pressed", String(active));
        });
        renderIndividualTierDetail();
      });
    });

    // Auditor Controls & Contextual Bar (Mobile #7)
    const codeArea = document.getElementById("audit-code-textarea");
    const ctxBar = document.getElementById("auditor-contextual-bar");
    if (codeArea) {
      codeArea.addEventListener("input", () => {
        state.isEditorDirty = codeArea.value !== state.lastSavedCode;
        if (ctxBar) ctxBar.hidden = !state.isEditorDirty;
      });
    }

    document.querySelectorAll("[data-cmap-mode]").forEach((btn) => {
      btn.addEventListener("click", () => {
        state.cmapMode = btn.getAttribute("data-cmap-mode") || "modern";
        document.querySelectorAll("[data-cmap-mode]").forEach((b) => {
          const active = b === btn;
          b.classList.toggle("is-active", active);
          b.setAttribute("aria-pressed", String(active));
        });
        runFortranAudit(true);
      });
    });

    document.getElementById("run-audit-btn")?.addEventListener("click", () => runFortranAudit(true));
    document.getElementById("ctx-run-audit-btn")?.addEventListener("click", () => runFortranAudit(true));

    const applyFixHandler = () => {
      if (codeArea && state.lastFixedCode) {
        codeArea.value = state.lastFixedCode;
        state.lastSavedCode = state.lastFixedCode;
        state.isEditorDirty = false;
        if (ctxBar) ctxBar.hidden = true;
        runFortranAudit(true);
        showToast("Applied Fortran auto-remediation");
      }
    };
    document.getElementById("apply-autofix-btn")?.addEventListener("click", applyFixHandler);
    document.getElementById("ctx-apply-fix-btn")?.addEventListener("click", applyFixHandler);

    document.getElementById("ctx-revert-btn")?.addEventListener("click", () => {
      if (codeArea) {
        codeArea.value = state.lastSavedCode;
        state.isEditorDirty = false;
        if (ctxBar) ctxBar.hidden = true;
        runFortranAudit(false);
        showToast("Reverted unsaved Fortran edits");
      }
    });
    document.getElementById("ctx-done-editing-btn")?.addEventListener("click", () => {
      if (codeArea) state.lastSavedCode = codeArea.value;
      state.isEditorDirty = false;
      if (ctxBar) ctxBar.hidden = true;
      runFortranAudit(true);
    });

    // Preset Bottom Sheet Events
    document.getElementById("open-preset-sheet-btn")?.addEventListener("click", openPresetSheet);
    document.getElementById("close-preset-sheet-btn")?.addEventListener("click", () => closePresetSheet(true));
    document.getElementById("cancel-preset-sheet-btn")?.addEventListener("click", () => closePresetSheet(true));
    document.getElementById("confirm-preset-sheet-btn")?.addEventListener("click", () => {
      applyPresetById(state.pendingSheetPresetId, true);
      closePresetSheet(true);
    });
    document.getElementById("preset-sheet-backdrop")?.addEventListener("click", (e) => {
      if (e.target.id === "preset-sheet-backdrop") {
        closePresetSheet(true);
      }
    });

    // Touch swipe-down gesture on bottom sheet header (Mobile #6)
    const dragZone = document.getElementById("sheet-drag-handle-zone");
    let touchStartY = null;
    if (dragZone) {
      dragZone.addEventListener(
        "touchstart",
        (e) => {
          if (e.touches && e.touches.length === 1) {
            touchStartY = e.touches[0].clientY;
          }
        },
        { passive: true }
      );
      dragZone.addEventListener(
        "touchend",
        (e) => {
          if (touchStartY !== null && e.changedTouches && e.changedTouches.length === 1) {
            const deltaY = e.changedTouches[0].clientY - touchStartY;
            if (deltaY > 48) {
              closePresetSheet(true);
            }
          }
          touchStartY = null;
        },
        { passive: true }
      );
    }

    const pSearch = document.getElementById("preset-search-input");
    if (pSearch) {
      pSearch.addEventListener("input", () => {
        state.presetSearchQuery = pSearch.value;
        renderPresetSheetList();
      });
    }
    document.getElementById("preset-search-clear")?.addEventListener("click", () => {
      state.presetSearchQuery = "";
      if (pSearch) {
        pSearch.value = "";
        pSearch.focus();
      }
      renderPresetSheetList();
    });
    document.getElementById("reset-preset-search-btn")?.addEventListener("click", () => {
      state.presetSearchQuery = "";
      state.presetCategory = "all";
      if (pSearch) pSearch.value = "";
      document.querySelectorAll("[data-preset-cat]").forEach((c) => {
        const isAll = c.getAttribute("data-preset-cat") === "all";
        c.classList.toggle("is-active", isAll);
        c.setAttribute("aria-pressed", String(isAll));
      });
      renderPresetSheetList();
    });
    document.querySelectorAll("[data-suggest-preset]").forEach((chip) => {
      chip.addEventListener("click", () => {
        const kw = chip.getAttribute("data-suggest-preset") || "";
        state.presetSearchQuery = kw;
        state.presetCategory = "all";
        if (pSearch) pSearch.value = kw;
        renderPresetSheetList();
      });
    });
    document.querySelectorAll("[data-preset-cat]").forEach((chip) => {
      chip.addEventListener("click", () => {
        state.presetCategory = chip.getAttribute("data-preset-cat") || "all";
        document.querySelectorAll("[data-preset-cat]").forEach((c) => {
          const active = c === chip;
          c.classList.toggle("is-active", active);
          c.setAttribute("aria-pressed", String(active));
        });
        renderPresetSheetList();
      });
    });

    // Global Keyboard Shortcuts (Escape to close overlays, Cmd/Ctrl+Enter to run)
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") {
        const sheetBackdrop = document.getElementById("preset-sheet-backdrop");
        if (sheetBackdrop && !sheetBackdrop.hidden) {
          e.preventDefault();
          closePresetSheet(true);
          return;
        }
        if (rtPopover && !rtPopover.hidden) {
          e.preventDefault();
          rtPopover.hidden = true;
          rtBtn?.setAttribute("aria-expanded", "false");
          rtBtn?.focus();
        }
      }
      if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
        if (state.activeView === "kernels") {
          e.preventDefault();
          executeActiveKernel(false);
        } else if (state.activeView === "auditor") {
          e.preventDefault();
          runFortranAudit(true);
        }
      }
    });

    window.addEventListener("resize", updateTableScrollHint);
    bindCopyButtons();

    // PDE Stencil, Benchmark Lab & Export Report Listeners (Phase 7)
    document.getElementById("export-report-btn")?.addEventListener("click", exportDiagnosticReport);
    document.getElementById("run-pde-btn")?.addEventListener("click", () => runPdeSimulation(true));
    document.getElementById("run-bench-btn")?.addEventListener("click", () => runLiveBenchmark(true));

    document.querySelectorAll("[data-pde-pulse]").forEach((btn) => {
      btn.addEventListener("click", () => {
        activePdePulse = btn.getAttribute("data-pde-pulse") || "gaussian";
        document.querySelectorAll("[data-pde-pulse]").forEach((b) => {
          const active = b === btn;
          b.classList.toggle("is-active", active);
          b.setAttribute("aria-pressed", String(active));
        });
        runPdeSimulation(true);
      });
    });

    document.querySelectorAll("[data-bench-workload]").forEach((btn) => {
      btn.addEventListener("click", () => {
        activeBenchWorkload = btn.getAttribute("data-bench-workload") || "dot_product";
        document.querySelectorAll("[data-bench-workload]").forEach((b) => {
          const active = b === btn;
          b.classList.toggle("is-active", active);
          b.setAttribute("aria-pressed", String(active));
        });
        runLiveBenchmark(true);
      });
    });

    // Phase 9: Matrix & Quadrature Explorer Listeners
    document.getElementById("run-quad-btn")?.addEventListener("click", () => runNumericsExplorer(true));
    document.querySelectorAll("[data-mat-preset]").forEach((btn) => {
      btn.addEventListener("click", () => {
        activeMatrixPreset = btn.getAttribute("data-mat-preset") || "rotation_scale";
        document.querySelectorAll("[data-mat-preset]").forEach((b) => {
          const active = b === btn;
          b.classList.toggle("is-active", active);
          b.setAttribute("aria-pressed", String(active));
        });
        runNumericsExplorer(true);
      });
    });
    document.querySelectorAll("[data-mat-order]").forEach((btn) => {
      btn.addEventListener("click", () => {
        activeMatrixOrder = btn.getAttribute("data-mat-order") || "F";
        document.querySelectorAll("[data-mat-order]").forEach((b) => {
          const active = b === btn;
          b.classList.toggle("is-active", active);
          b.setAttribute("aria-pressed", String(active));
        });
        runNumericsExplorer(true);
      });
    });
    document.querySelectorAll("[data-quad-func]").forEach((btn) => {
      btn.addEventListener("click", () => {
        activeQuadFunc = btn.getAttribute("data-quad-func") || "sin_pi";
        document.querySelectorAll("[data-quad-func]").forEach((b) => {
          const active = b === btn;
          b.classList.toggle("is-active", active);
          b.setAttribute("aria-pressed", String(active));
        });
        runNumericsExplorer(true);
      });
    });

    // Load initial API state
    try {
      const [healthResp, kernelsResp, compResp] = await Promise.all([
        fetch("/api/v1/health"),
        fetch("/api/v1/kernels"),
        fetch("/api/v1/compute/prod", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ kernel_id: "prodintent", x: 3.0, y: 2.0, z_init: 12345.0, compare_all: true }),
        }),
      ]);

      if (healthResp.ok) {
        const h = await healthResp.json();
        document.getElementById("rt-python-ver").textContent = h.python_version;
        document.getElementById("rt-numpy-ver").textContent = h.numpy_version;
        document.getElementById("runtime-platform-label").textContent = `${h.platform} • NumPy ABI`;
      }
      if (kernelsResp.ok) {
        const kd = await kernelsResp.json();
        state.kernels = kd.kernels || [];
        renderKernelSelector();
      }
      if (compResp.ok) {
        const cd = await compResp.json();
        renderPrimaryTelemetry(cd.primary);
        renderComparisonTable(cd.comparison.results);
        // Clear initial auto-seed from session log so First-Use Empty State is shown cleanly on first visit
        await fetch("/api/v1/history", { method: "DELETE" });
        await refreshHistory();
      }
    } catch (_e) {
      // ignore
    }

    await Promise.all([
      loadPrecisionData(),
      loadPresets(),
      runPdeSimulation(false),
      runLiveBenchmark(false),
      runNumericsExplorer(false),
    ]);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
