(() => {
    const content = document.getElementById("training-today-content");
    const loading = document.getElementById("training-today-loading");
    if (!content) return;

    // Timeout: nach 60 Sekunden abbrechen
    const TIMEOUT_MS = 60_000;

    let timedOut = false;
    const controller = new AbortController();
    const timer = setTimeout(() => {
        timedOut = true;
        controller.abort();
        loading.style.display = "none";
        content.innerHTML =
            '<p class="placeholder">Trainingsempfehlung aktuell nicht verfügbar. <a href="/">Dashboard neu laden</a>.</p>';
    }, TIMEOUT_MS);

    fetch("/dashboard/training-today", {
        headers: { Accept: "text/html" },
        signal: controller.signal,
    })
        .then((response) => {
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            return response.text();
        })
        .then((html) => {
            if (timedOut) return;
            clearTimeout(timer);
            loading.style.display = "none";
            content.innerHTML = html;
        })
        .catch(() => {
            if (timedOut) return;
            clearTimeout(timer);
            loading.style.display = "none";
            content.innerHTML =
                '<p class="placeholder">Trainingsempfehlung aktuell nicht verfügbar.</p>';
        });
})();
