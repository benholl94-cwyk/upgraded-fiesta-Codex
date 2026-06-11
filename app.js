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
 * Retrieve a DOM element by CSS selector or throw if not found.
 * @param {string} selector - CSS selector of the required element.
 * @returns {Element} The matching DOM element.
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
 * Selects a configuration profile and updates the UI to match it.
 *
 * Activates the profile identified by `name` (falls back to `"minimal"` when the key is missing or unknown),
 * replaces the plan and autonomy-checks lists with the profile's steps and checks (checkboxes start checked),
 * updates all `.profile` buttons' active state and `aria-pressed` attributes, and regenerates the script for the chosen profile.
 * @param {string} name - The profile key to activate (e.g., `"minimal"`, `"linux"`, `"hybrid"`).
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
 * Create a filesystem-safe project folder name from an arbitrary string.
 * Trims whitespace, replaces disallowed characters with '-', collapses multiple '-',
 * trims leading/trailing '.' and '-', and limits length to 48 characters.
 * @param {string} value - The raw project name input.
 * @returns {string} A sanitized folder name; returns `'iphone-dev-check'` if the result is empty.
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
 * Generate and display the shell script for the selected profile.
 *
 * Sanitizes the current project name, builds a common shell script, appends
 * profile-specific extras, writes the script into the `scriptOutput` element,
 * and updates the `projectName` input with the sanitized name.
 *
 * @param {string} [profileName=document.querySelector('.profile.active')?.dataset.profile || 'minimal'] - Profile key that selects which extra instructions to append; falls back to `minimal` when unknown.
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
 * Copy the currently rendered script to the clipboard and update the UI with the operation result.
 *
 * On success, sets the copy status element to a success message; on failure, sets a fallback message
 * instructing the user to copy the script manually.
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
 * Retrieve the guide text used for QA checks and script generation.
 *
 * Attempts to fetch 'docs/iphone-local-dev-setup.md' without cache and returns its text.
 * If the fetch fails or the response is not OK, returns document.body.innerText as a fallback.
 *
 * @returns {string} The guide text to be analyzed and displayed.
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
 * Validate top-level numbered headings (level-2) in the provided Markdown text.
 *
 * @param {string} text - Markdown content to scan for level-2 headings of the form `## 1. Title`.
 * @returns {{label: string, ok: boolean, detail: string}} An object describing the check:
 *  - `label`: title of the check,
 *  - `ok`: `true` if the extracted numbers form a consecutive sequence starting at 1, `false` otherwise,
 *  - `detail`: either a success summary like "`N` Abschnitte geprüft." or a description of the found sequence.
 */
function checkNumbering(text) {
  const headings = [...text.matchAll(/^## (\d+)\. /gm)].map((match) => Number(match[1]));
  if (headings.length === 0) return { label: 'Top-Level-Nummerierung gefunden', ok: false, detail: 'Keine nummerierten Abschnitte gefunden.' };
  const expected = headings.map((_, index) => index + 1);
  const ok = headings.every((value, index) => value === expected[index]);
  return { label: 'Durchgehende Top-Level-Nummerierung', ok, detail: ok ? `${headings.length} Abschnitte geprüft.` : `Gefunden: ${headings.join(', ')}` };
}

/**
 * Create a list item element representing a QA result.
 *
 * The returned <li> contains a leading dot <span> whose class reflects pass/fail,
 * followed by text formatted as: "Label: OK|Prüfen — detail".
 *
 * @param {Object} options - Options for the result item.
 * @param {string} options.label - Short title for the check.
 * @param {boolean} options.ok - Whether the check passed.
 * @param {string} options.detail - Additional information or matched text.
 * @param {string} [options.level='ok'] - Severity level used for the dot when `ok` is false.
 * @returns {HTMLLIElement} The constructed list item element.
 */
function resultItem({ label, ok, detail, level = 'ok' }) {
  const li = document.createElement('li');
  const dot = document.createElement('span');
  dot.className = `dot ${ok ? 'ok' : level}`;
  li.append(dot, `${label}: ${ok ? 'OK' : 'Prüfen'} — ${detail}`);
  return li;
}

/**
 * Run the configured QA checks on the guide text and render the results into the QA results list.
 *
 * Loads the guide text, evaluates each risky pattern plus the heading-numbering check, and replaces
 * the contents of the QA results element with the generated result items.
 */
async function runQa() {
  const text = await loadGuideText();
  const results = riskyPatterns.map((rule) => {

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
