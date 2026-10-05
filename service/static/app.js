const EXPERT = {
  joinable: "Could join",
  excluded: "Right disease, a rule fails",
  irrelevant: "Not this disease",
};

function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (ch) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[ch]));
}

function expertLabel(verdict) {
  return verdict ? EXPERT[verdict] || verdict : "Not judged";
}

function readerLabel(row) {
  if (row.reader_error) return row.reader_error;
  if (!row.reader) return "No stored reader reply";
  const verdict = row.reader.compatible_unless_contradicted;
  if (verdict === "excluded") return "Express contradiction";
  if (verdict === "compatible") return "No express contradiction in the note";
  return "No stored reader reply";
}

function sectionLabel(section) {
  if (section === "inclusion") return "Inclusion";
  if (section === "exclusion") return "Exclusion";
  return "Unsplit";
}

function verdictLabel(section, verdict) {
  if (!verdict) return "Not read";
  if (verdict === "not_enough_information") return "Note does not settle this";
  if (section === "exclusion") {
    if (verdict === "met") return "Exclusion appears present";
    if (verdict === "not_met") return "Exclusion does not appear";
  }
  if (verdict === "met") return "Note supports this";
  if (verdict === "not_met") return "Note conflicts with this";
  return verdict;
}

async function getJson(url, options) {
  const response = await fetch(url, options);
  const body = await response.json();
  if (!response.ok) {
    throw new Error(body.error || response.statusText);
  }
  return body;
}

function setMode(mode) {
  const el = document.getElementById("mode");
  el.textContent = mode || "unknown";
  el.classList.toggle("live", mode === "live");
}

function renderPatients(patients) {
  const root = document.getElementById("patients");
  root.innerHTML = patients
    .map(
      (p) =>
        `<button type="button" data-id="${esc(p.patient_id)}">
          <strong>Note ${esc(p.patient_id)}</strong>
          ${esc(p.summary || p.first_line || "")}
        </button>`
    )
    .join("");
  root.querySelectorAll("button").forEach((btn) => {
    btn.addEventListener("click", () => selectPatient(btn.dataset.id, patients));
  });
}

function showNote(patient) {
  const el = document.getElementById("note");
  el.hidden = false;
  el.textContent = patient.note || "";
}

let lastResults = [];

async function selectPatient(patientId, patients) {
  const patient = patients.find((p) => p.patient_id === patientId);
  document.querySelectorAll("#patients button").forEach((btn) => {
    btn.setAttribute("aria-pressed", String(btn.dataset.id === patientId));
  });
  showNote(patient);
  clearDetail();
  document.getElementById("results").innerHTML = "";
  document.getElementById("status").textContent = "Running search and ranking…";
  try {
    const payload = await getJson("/v1/match", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ patient_id: patientId, depth: 10 }),
    });
    setMode(payload.model_mode);
    if (payload.disclaimer) {
      document.getElementById("disclaimer").textContent = payload.disclaimer;
    }
    lastResults = payload.results || [];
    const ms = payload.timings && payload.timings.total_ms;
    const replay = payload.model_mode === "replay";
    document.getElementById("status").textContent =
      `Search returned ${payload.n_retrieved} trials; showing ${lastResults.length}.` +
      (ms != null ? ` Ran in ${ms} ms.` : "") +
      (replay ? " Reader replies were replayed." : "");
    renderResults();
  } catch (err) {
    document.getElementById("status").innerHTML =
      `<span class="error">${esc(err.message)}</span>`;
  }
}

function renderResults() {
  const root = document.getElementById("results");
  root.innerHTML = lastResults
    .map(
      (row, i) =>
        `<li>
          <button type="button" class="row" data-i="${i}">
            <div class="nct">${esc(row.nct_id)}</div>
            <div>${esc(row.title || "(no title)")}</div>
            <div class="marks">
              <span class="mark">Expert: <strong>${esc(expertLabel(row.expert_verdict))}</strong></span>
              <span class="mark">Reader: <strong>${esc(readerLabel(row))}</strong></span>
            </div>
          </button>
        </li>`
    )
    .join("");
  root.querySelectorAll("button.row").forEach((btn) => {
    btn.addEventListener("click", () => showDetail(Number(btn.dataset.i)));
  });
}

function clearDetail() {
  document.getElementById("detail-heading").textContent = "Requirements";
  document.getElementById("detail-meta").textContent =
    "Click a trial to see its written inclusion and exclusion rules.";
  document.getElementById("detail-body").innerHTML = "";
}

function showDetail(index) {
  const row = lastResults[index];
  if (!row) return;
  document.querySelectorAll("#results button.row").forEach((btn, i) => {
    btn.setAttribute("aria-pressed", String(i === index));
  });
  document.getElementById("detail-heading").textContent = row.title || row.nct_id;
  const bits = [row.nct_id];
  if (row.splitter_mode === "no_header") {
    bits.push("eligibility text was not split into inclusion and exclusion");
  }
  document.getElementById("detail-meta").textContent = bits.join(" · ");

  const byId = {};
  for (const judgement of (row.reader && row.reader.rules) || []) {
    byId[judgement.rule_id] = judgement;
  }
  const criteria = row.criteria && row.criteria.length
    ? row.criteria
    : (row.reader && row.reader.rules) || [];
  const body = document.getElementById("detail-body");
  if (!criteria.length) {
    body.innerHTML = `<p class="quiet">No written criteria were split from this trial.</p>`;
    return;
  }
  body.innerHTML = criteria
    .map((rule) => {
      const judgement = byId[rule.rule_id] || rule;
      const flagged = Boolean(judgement.quote_flagged);
      const quote = judgement.quote
        ? `<p class="quote${flagged ? " flagged" : ""}">${esc(judgement.quote)}
            <span class="quiet"> (${esc(judgement.quote_source === "patient" ? "from the note" : "from the trial")}${
              flagged ? "; flagged — not a clean span of the named source" : ""
            })</span></p>`
        : `<p class="quiet">No quote</p>`;
      return `<article class="rule">
        <div class="rule-head">${esc(sectionLabel(rule.section))} · ${esc(
          verdictLabel(rule.section, judgement.verdict)
        )}</div>
        <p>${esc(rule.text || judgement.text || "")}</p>
        ${quote}
      </article>`;
    })
    .join("");
}

async function boot() {
  try {
    const health = await getJson("/health");
    setMode(health.model_mode);
    if (health.disclaimer) {
      document.getElementById("disclaimer").textContent = health.disclaimer;
    }
    const data = await getJson("/v1/patients");
    renderPatients(data.patients || []);
  } catch (err) {
    document.getElementById("status").innerHTML =
      `<span class="error">${esc(err.message)}</span>`;
  }
}

boot();
