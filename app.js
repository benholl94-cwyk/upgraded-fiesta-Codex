const profiles = {
  minimal: {
    steps: [
      'Working Copy installieren und Git-Konto verbinden.',
      'Textastic oder Code App installieren und Repository als externen Ordner öffnen.',
      'a-Shell öffnen und python3 --version ausführen.',
      'README.md ändern, Diff in Working Copy prüfen, committen und pushen.'
    ],
    checks: ['Kein Build-Schritt', 'Funktioniert offline für Text/kleine Skripte', 'Git bleibt die Synchronisationsquelle']
  },
  linux: {
    steps: [
      'iSH installieren und apk update ausführen.',
      'Basiswerkzeuge mit apk add git openssh curl wget nano vim python3 py3-pip nodejs npm make installieren.',
      'Git-Identität und SSH-Key in iSH konfigurieren.',
      'Kleine Python-/Node-Checks ausführen, bevor große Abhängigkeiten installiert werden.'
    ],
    checks: ['Alpine-nahe Shell', 'Lokale Paketverwaltung', 'Nicht für schwere Builds optimiert']
  },
  hybrid: {
    steps: [
      'iPhone als Editor- und Git-Client nutzen.',
      'Remote-Host per SSH vorbereiten und Repository in ~/projects klonen.',
      'Builds, Docker, Datenbanken und lange Tests remote ausführen.',
      'Änderungen über Git zwischen iPhone, Remote-Host und Plattform synchronisieren.'
    ],
    checks: ['Stabil für große Projekte', 'Benötigt Remote-Host', 'Beste Option für CI-nahe Arbeit']
  }
};

const riskyPatterns = [
  { label: 'Foto-/OCR-Artefakte', pattern: /\b(Foto|photo|Bildfehler|OCR)\b/i, level: 'warn' },
  { label: 'TODO/FIXME-Reste', pattern: /\b(TODO|FIXME|XXX)\b/i, level: 'warn' },
  { label: 'Blinde Remote-Ausführung', pattern: /(curl|wget).*(\|\s*(sh|bash))/i, level: 'bad' },
  { label: 'Platzhalter-Domain example.com', pattern: /example\.com/i, level: 'warn' },
  { label: 'Unklare None-Artefakte', pattern: /\bNone\b/i, level: 'warn' }
];

/**
 * Selects a DOM element by CSS selector and ensures it exists.
 * @param {string} selector - CSS selector used with document.querySelector.
 * @returns {Element} The found DOM element.
 * @throws {Error} If no element matches the selector.
 */
function requiredElement(selector) {
  const element = document.querySelector(selector);
  if (!element) {
    throw new Error(`Required element missing: ${selector}`);
  }
  return element;
}

const planOutput = requiredElement('#planOutput');
const autonomyChecks = requiredElement('#autonomyChecks');
const scriptOutput = requiredElement('#scriptOutput');
const projectName = requiredElement('#projectName');
const copyStatus = requiredElement('#copyStatus');
const qaResults = requiredElement('#qaResults');

/**
 * Activate a setup profile and update the UI to reflect that selection.
 *
 * Updates the displayed plan steps and prechecked autonomy checklist, toggles profile button states, and regenerates the script for the active profile.
 * @param {string} name - Desired profile key ('minimal', 'linux', or 'hybrid'); falls back to 'minimal' when the key is unrecognized.
 */
function setProfile(name) {
  const profileName = profiles[name] ? name : 'minimal';
  const profile = profiles[profileName];
  planOutput.replaceChildren(...profile.steps.map((step) => {
    const li = document.createElement('li');
    li.textContent = step;
    return li;
  }));

  autonomyChecks.replaceChildren(...profile.checks.map((check) => {
    const label = document.createElement('label');
    const box = document.createElement('input');
    box.type = 'checkbox';
    box.checked = true;
    label.append(box, ` ${check}`);
    return label;
  }));

  document.querySelectorAll('.profile').forEach((button) => {
    const active = button.dataset.profile === profileName;
    button.classList.toggle('active', active);
    button.setAttribute('aria-pressed', String(active));
  });
  renderScript(profileName);
}

/**
 * Normalize a user-provided project name into a filesystem- and variable-safe identifier.
 * @param {string} value - The raw project name input.
 * @returns {string} The sanitized project name: trims whitespace, replaces characters not in `[a-zA-Z0-9._-]` with `-`, collapses repeated dashes, removes leading/trailing `.` or `-`, and truncates to 48 characters; returns `'iphone-dev-check'` if the result is empty.
 */
function safeProjectName(value) {
  const cleaned = value
    .trim()
    .replace(/[^a-zA-Z0-9._-]/g, '-')
    .replace(/-+/g, '-')
    .replace(/^[.-]+|[.-]+$/g, '')
    .slice(0, 48);
  return cleaned || 'iphone-dev-check';
}

/**
 * Generate the shell script for the selected profile and update the UI with the script and sanitized project name.
 *
 * Builds a project bootstrap script (common setup, README, hello.py) and appends profile-specific extras for
 * "minimal", "linux", or "hybrid", then writes the result into the page and sets the project name input to a
 * filesystem-safe value.
 *
 * @param {string} [profileName=document.querySelector('.profile.active')?.dataset.profile || 'minimal'] - Profile key to render; expected values: "minimal", "linux", or "hybrid".
 */
function renderScript(profileName = document.querySelector('.profile.active')?.dataset.profile || 'minimal') {
  const name = safeProjectName(projectName.value);
  const common = `set -eu\numask 077\nPROJECT="${name}"\nmkdir -p "$HOME/Developer/scratch/$PROJECT"\ncd "$HOME/Developer/scratch/$PROJECT"\ncat > README.md <<'MD'\n# ${name}\n\nAutonom erzeugtes iPhone-Entwicklungsprojekt.\nMD\ncat > hello.py <<'PY'\nprint("iPhone Direct-Inject OK")\nPY\npython3 hello.py`;

  const extras = {
    minimal: '\nprintf "\\nMinimalprofil bereit. Öffne den Ordner im Editor und committe über Working Copy.\\n"',
    linux: '\nprintf "\\nOptional in iSH ausführen: apk update && apk add git openssh python3 nodejs npm\\n"',
    hybrid: '\ncat > remote-checklist.txt <<\'TXT\'\nssh dev@dein-host\nmkdir -p ~/projects\n# git clone git@github.com:dein-name/dein-repo.git\nTXT\nprintf "\\nHybridprofil bereit. Siehe remote-checklist.txt.\\n"'
  };

  scriptOutput.textContent = `${common}${extras[profileName] || extras.minimal}\n`;
  projectName.value = name;
}

/**
 * Copy the generated script to the clipboard and update the copy status message.
 *
 * Attempts to write the current script text to the navigator clipboard. On success sets
 * `copyStatus.textContent` to "Skript wurde kopiert."; on failure sets it to
 * "Kopieren nicht möglich. Bitte Skript manuell markieren.".
 */
async function copyScript() {
  try {
    await navigator.clipboard.writeText(scriptOutput.textContent);
    copyStatus.textContent = 'Skript wurde kopiert.';
  } catch {
    copyStatus.textContent = 'Kopieren nicht möglich. Bitte Skript manuell markieren.';
  }
}

/**
 * Load the project's guide Markdown and fall back to the document text if fetching fails.
 * @returns {string} The guide content as a string; the fetched markdown on success, or the page's visible text if loading fails.
 */
async function loadGuideText() {
  try {
    const response = await fetch('docs/iphone-local-dev-setup.md', { cache: 'no-cache' });
    if (!response.ok) throw new Error('Guide nicht ladbar');
    return await response.text();
  } catch {
    return document.body.innerText;
  }
}

/**
 * Check top-level numbered headings in a markdown document for a contiguous sequence starting at 1.
 *
 * @param {string} text - Markdown content to scan for top-level headings of the form "## <number>. ".
 * @returns {{label: string, ok: boolean, detail: string}} An object describing the check:
 *   - `label`: human-readable check title,
 *   - `ok`: `true` if the extracted heading numbers form the sequence 1..N in order, `false` otherwise,
 *   - `detail`: when `ok` is `true`, a summary like "`<N> Abschnitte geprüft.`"; when no headings are found, a message stating that; otherwise a comma-separated list of found numbers.
 */
function checkNumbering(text) {
  const headings = [...text.matchAll(/^## (\d+)\. /gm)].map((match) => Number(match[1]));
  if (headings.length === 0) return { label: 'Top-Level-Nummerierung gefunden', ok: false, detail: 'Keine nummerierten Abschnitte gefunden.' };
  const expected = headings.map((_, index) => index + 1);
  const ok = headings.every((value, index) => value === expected[index]);
  return { label: 'Durchgehende Top-Level-Nummerierung', ok, detail: ok ? `${headings.length} Abschnitte geprüft.` : `Gefunden: ${headings.join(', ')}` };
}

/**
 * Create a DOM list item representing a QA finding.
 * @param {{label: string, ok: boolean, detail: string, level?: string}} options - Properties describing the finding.
 * @param {string} options.label - The visible label for the finding.
 * @param {boolean} options.ok - Whether the check passed.
 * @param {string} options.detail - Additional detail or context for the finding.
 * @param {string} [options.level='ok'] - Severity level used for the status dot when `ok` is false.
 * @returns {HTMLLIElement} The constructed `<li>` element containing a status dot and descriptive text.
 */
function resultItem({ label, ok, detail, level = 'ok' }) {
  const li = document.createElement('li');
  const dot = document.createElement('span');
  dot.className = `dot ${ok ? 'ok' : level}`;
  li.append(dot, `${label}: ${ok ? 'OK' : 'Prüfen'} — ${detail}`);
  return li;
}

/**
 * Run the QA suite against the guide text and display findings in the QA results area.
 *
 * Loads the guide document, evaluates each configured risky pattern and a top-level
 * heading-numbering check, then renders the aggregated findings into the `qaResults`
 * DOM element.
 */
async function runQa() {
  const text = await loadGuideText();
  const results = riskyPatterns.map((rule) => {
    const match = text.match(rule.pattern);
    return {
      label: rule.label,
      ok: !match,
      detail: match ? `Treffer „${match[0]}“ gefunden.` : 'Keine Treffer.',
      level: rule.level
    };
  });
  results.push(checkNumbering(text));
  qaResults.replaceChildren(...results.map(resultItem));
}

document.querySelectorAll('.profile').forEach((button) => {
  button.addEventListener('click', () => setProfile(button.dataset.profile));
});
projectName.addEventListener('input', () => renderScript());
requiredElement('#copyScript').addEventListener('click', copyScript);

if ('serviceWorker' in navigator && location.protocol !== 'file:') {
  navigator.serviceWorker.register('service-worker.js').catch(() => {});
}

setProfile('minimal');
runQa();
