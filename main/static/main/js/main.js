// Timezone settings
const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
document.cookie = "django_timezone=" + timezone + "; path=/; SameSite=Lax";
console.log('Timezone set ', timezone)

// Card grids: show only whole rows, up to the data-max-rows the grid asks for.
// The column count is whatever the viewport gives us, so it is measured here
// rather than guessed on the server.
function trimCardGrids() {
    document.querySelectorAll('.hp-grid[data-max-rows]').forEach(function (grid) {
        const maxRows = parseInt(grid.dataset.maxRows, 10);
        const items = grid.children;
        const cols = getComputedStyle(grid).gridTemplateColumns.split(' ').length;
        const visible = items.length < cols
            ? items.length
            : Math.min(maxRows * cols, Math.floor(items.length / cols) * cols);
        for (let i = 0; i < items.length; i++) {
            items[i].hidden = i >= visible;
        }
    });
}

let trimCardGridsTimer;
window.addEventListener('resize', function () {
    clearTimeout(trimCardGridsTimer);
    trimCardGridsTimer = setTimeout(trimCardGrids, 150);
});
document.addEventListener('DOMContentLoaded', trimCardGrids);
