const taskChecks = [...document.querySelectorAll('.task-check')];
const cookButton = document.querySelector('[data-cook-mode]');
const cookDock = document.querySelector('[data-cook-dock]');
const progressLabel = document.querySelector('[data-progress-label]');
const progressBar = document.querySelector('[data-progress-bar]');
const wakeStatus = document.querySelector('[data-wake-status]');
const recipeId = document.body.dataset.recipeId;
const storageKey = recipeId ? `tavola-progress-${recipeId}` : null;
let wakeLock = null;

function saveProgress() {
  if (!storageKey) return;
  try {
    localStorage.setItem(storageKey, JSON.stringify(taskChecks.map(check => check.checked)));
  } catch (error) {
    // Progress persistence is optional when storage is unavailable.
  }
}

function restoreProgress() {
  if (!storageKey) return;
  try {
    const saved = JSON.parse(localStorage.getItem(storageKey));
    if (Array.isArray(saved)) {
      taskChecks.forEach((check, index) => { check.checked = Boolean(saved[index]); });
    }
  } catch (error) {
    // Ignore invalid or unavailable local storage.
  }
}

function updateProgress() {
  if (!taskChecks.length) return;
  const completed = taskChecks.filter(check => check.checked).length;
  const percentage = Math.round((completed / taskChecks.length) * 100);
  if (progressLabel) progressLabel.textContent = `${percentage}%`;
  if (progressBar) progressBar.style.width = `${percentage}%`;
  saveProgress();
}

taskChecks.forEach(check => check.addEventListener('change', updateProgress));

document.querySelector('[data-check-all]')?.addEventListener('click', event => {
  const ingredientChecks = [...document.querySelectorAll('.ingredient-checks .task-check')];
  const shouldCheck = ingredientChecks.some(check => !check.checked);
  ingredientChecks.forEach(check => { check.checked = shouldCheck; });
  event.currentTarget.textContent = shouldCheck ? 'Azzera spunte' : 'Spunta tutto';
  updateProgress();
});

document.querySelector('[data-print]')?.addEventListener('click', () => window.print());

async function setCookingMode(active) {
  document.body.classList.toggle('cooking-mode', active);
  cookDock?.classList.toggle('is-visible', active);
  if (active) {
    if ('wakeLock' in navigator) {
      try {
        wakeLock = await navigator.wakeLock.request('screen');
        if (wakeStatus) wakeStatus.textContent = 'schermo attivo';
      } catch (error) {
        if (wakeStatus) wakeStatus.textContent = 'modalità attiva';
      }
    }
    document.querySelector('.cooking-step:not(:has(input:checked))')?.scrollIntoView({ behavior: 'smooth', block: 'center' });
  } else if (wakeLock) {
    await wakeLock.release();
    wakeLock = null;
  }
}

cookButton?.addEventListener('click', () => setCookingMode(true));
document.querySelector('[data-exit-cook]')?.addEventListener('click', () => setCookingMode(false));
document.querySelector('[data-next-step]')?.addEventListener('click', () => {
  const nextStep = document.querySelector('.cooking-step:not(:has(input:checked))');
  nextStep?.scrollIntoView({ behavior: 'smooth', block: 'center' });
});

document.querySelector('[data-admin-photo]')?.addEventListener('change', event => {
  const file = event.target.files[0];
  const label = document.querySelector('[data-admin-photo-label]');
  const message = document.querySelector('[data-admin-photo-message]');
  const allowedTypes = ['image/jpeg', 'image/png', 'image/webp', 'image/avif'];
  const error = file && (
    file.size > 4_000_000
      ? 'La foto supera 4 MB. Scegline una più leggera.'
      : !allowedTypes.includes(file.type)
        ? 'Formato non supportato. Usa JPG, PNG, WebP o AVIF.'
        : ''
  );
  if (error) event.target.value = '';
  if (label) label.textContent = error ? 'Scegli un’altra foto' : file?.name || 'Scegli foto';
  if (message) {
    message.textContent = error || '';
    message.hidden = !error;
  }
});

restoreProgress();
updateProgress();