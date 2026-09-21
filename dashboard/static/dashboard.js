(() => {
    const target = document.getElementById("training-today-content");
    if (!target) return;

    fetch("/dashboard/training-today", {
        headers: {"Accept": "text/html"},
    })
        .then((response) => {
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            return response.text();
        })
        .then((html) => {
            target.innerHTML = html;
        })
        .catch(() => {
            target.innerHTML = '<p class="placeholder">Trainingsempfehlung aktuell nicht verfügbar.</p>';
        });
})();
