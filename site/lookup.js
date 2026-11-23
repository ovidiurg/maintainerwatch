"use strict";

(() => {
  const form = document.getElementById("lookup-form");
  if (!form) return;

  const systemInput = document.getElementById("lookup-system");
  const nameInput = document.getElementById("lookup-name");
  const submitButton = form.querySelector('button[type="submit"]');
  const status = document.getElementById("lookup-status");
  const result = document.getElementById("lookup-result");
  const kicker = document.getElementById("lookup-kicker");
  const packageName = document.getElementById("lookup-package");
  const band = document.getElementById("lookup-band");
  const score = document.getElementById("lookup-score");
  const confidence = document.getElementById("lookup-confidence");
  const coverage = document.getElementById("lookup-coverage");
  const riskType = document.getElementById("lookup-risk-type");
  const signalsWrap = document.getElementById("lookup-signals-wrap");
  const signalsList = document.getElementById("lookup-signals");
  const foot = document.getElementById("lookup-foot");

  const state = {
    packages: null,
    generatedAt: null,
    modelVersion: null,
    pending: null,
  };

  const setStatus = (text) => {
    status.textContent = text;
  };

  const formatDate = (value) => {
    if (!value) return "unknown date";
    const parsed = new Date(value);
    return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString();
  };

  const normalize = (value) => String(value || "").trim().toLowerCase();

  const hideResult = () => {
    result.hidden = true;
  };

  const render = (pkg) => {
    kicker.textContent = `${pkg.system} package`;
    packageName.textContent = pkg.name;

    const knownBands = ["high", "medium", "low"];
    const bandName = knownBands.includes(pkg.band) ? pkg.band : "unknown";
    band.className = `band-pill band-${bandName}`;
    band.textContent = pkg.band || "unknown";

    score.textContent = Number.isFinite(Number(pkg.score))
      ? Number(pkg.score).toFixed(1)
      : "unknown";
    confidence.textContent = pkg.confidence || "unknown";
    coverage.textContent = Number.isFinite(Number(pkg.coverage))
      ? `${Math.round(Number(pkg.coverage) * 100)}%`
      : "unknown";
    riskType.textContent = pkg.risk_type || "No high/medium risk type";

    const topSignals = Array.isArray(pkg.top_signals) ? pkg.top_signals : [];
    signalsList.replaceChildren();
    if (topSignals.length) {
      signalsWrap.hidden = false;
      for (const signal of topSignals) {
        const item = document.createElement("li");
        const label = String(signal.name || "signal").replaceAll("_", " ");
        const value = Number.isFinite(Number(signal.value))
          ? Number(signal.value).toFixed(2)
          : "unknown";
        item.textContent = `${label}: ${value}`;
        signalsList.append(item);
      }
    } else {
      signalsWrap.hidden = true;
    }

    const generated = formatDate(state.generatedAt);
    foot.textContent = `Public index generated ${generated} · model ${state.modelVersion || "unknown"} · static snapshot, not a live verdict.`;

    result.hidden = false;
    setStatus("Result loaded from the public compact index.");
  };

  const lookup = (system, rawName, updateUrl = true) => {
    if (!state.packages) {
      state.pending = { system, name: rawName };
      setStatus("Index is still loading…");
      return;
    }

    const name = String(rawName || "").trim();
    if (!name) {
      hideResult();
      setStatus("Enter a package name.");
      return;
    }

    const key = `${system}:${normalize(name)}`;
    const pkg = state.packages.get(key);
    if (!pkg) {
      hideResult();
      setStatus(`No entry for ${system}/${name} in this snapshot. Try another ecosystem or check the full dataset release.`);
      return;
    }

    render(pkg);
    if (updateUrl) {
      const url = new URL(window.location.href);
      url.searchParams.set("system", system);
      url.searchParams.set("name", pkg.name);
      url.hash = "lookup";
      window.history.replaceState(null, "", url);
    }
  };

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    lookup(systemInput.value, nameInput.value);
  });

  submitButton.disabled = true;

  fetch("maintainerwatch-index.json", { cache: "no-cache" })
    .then((response) => {
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return response.json();
    })
    .then((doc) => {
      const packages = new Map();
      for (const pkg of Object.values(doc.packages || {})) {
        if (!pkg || !pkg.system || !pkg.name) continue;
        packages.set(`${pkg.system}:${normalize(pkg.name)}`, pkg);
      }
      state.packages = packages;
      state.generatedAt = doc.generated_at || null;
      state.modelVersion = doc.model_version || null;
      submitButton.disabled = false;

      const count = Number(doc.counts && doc.counts.packages) || packages.size;
      setStatus(`Index loaded: ${count.toLocaleString()} packages · model ${state.modelVersion || "unknown"}.`);

      const params = new URLSearchParams(window.location.search);
      const requestedSystem = params.get("system");
      const requestedName = params.get("name");
      if (requestedSystem && requestedName) {
        systemInput.value = requestedSystem;
        nameInput.value = requestedName;
        lookup(requestedSystem, requestedName, false);
      } else if (state.pending) {
        lookup(state.pending.system, state.pending.name);
        state.pending = null;
      }
    })
    .catch((error) => {
      submitButton.disabled = false;
      setStatus(`Lookup index unavailable in this local copy (${error.message}). Use the published index from the release page.`);
    });
})();
