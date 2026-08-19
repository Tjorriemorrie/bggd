// Timezone settings
const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
document.cookie = 'django_timezone=' + timezone + '; path=/; SameSite=Lax';

// Index rail: collapses behind the toggle below the rail breakpoint.
function initNavToggle() {
    const toggle = document.getElementById('nav-toggle');
    const rail = document.getElementById('nav-rail');
    if (!toggle || !rail) return;

    const close = function () {
        toggle.classList.remove('nav-toggle-open');
        toggle.setAttribute('aria-expanded', 'false');
        rail.classList.remove('rail-open');
    };

    toggle.addEventListener('click', function () {
        const open = rail.classList.toggle('rail-open');
        toggle.classList.toggle('nav-toggle-open', open);
        toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
    });

    rail.querySelectorAll('a').forEach(function (a) {
        a.addEventListener('click', close);
    });

    window.addEventListener('resize', function () {
        if (window.innerWidth > 999.98) close();
    });
}

// The narrow sheet, matching the two-column tray in the stylesheet. A row there
// carries a third of what a wide row does, so the row allowance is doubled to
// keep a tray about as deep as it reads on a wide sheet.
const NARROW = '(max-width: 619.98px)';

// Counter trays: show only whole rows, up to the data-max-rows the tray asks
// for. The column count is whatever the viewport gives us, so it is measured
// here rather than guessed on the server. A tray without the attribute (the
// pinned tray) is never trimmed: every pin the visitor placed is shown.
function trimTrays() {
    const rows = window.matchMedia(NARROW).matches ? 2 : 1;
    document.querySelectorAll('.tray[data-max-rows]').forEach(function (tray) {
        const maxRows = parseInt(tray.dataset.maxRows, 10) * rows;
        const items = tray.children;
        const cols = getComputedStyle(tray).gridTemplateColumns.split(' ').length;
        const visible = items.length < cols
            ? items.length
            : Math.min(maxRows * cols, Math.floor(items.length / cols) * cols);
        for (let i = 0; i < items.length; i++) {
            items[i].hidden = i >= visible;
        }
    });
}

// Stock tabs on the game sheet: in stock / out of stock rosters.
function initTabs() {
    const tabs = Array.prototype.slice.call(document.querySelectorAll('[role="tab"]'));
    if (!tabs.length) return;

    const select = function (tab) {
        tabs.forEach(function (t) {
            const panel = document.getElementById(t.getAttribute('aria-controls'));
            const on = t === tab;
            t.setAttribute('aria-selected', on ? 'true' : 'false');
            t.setAttribute('tabindex', on ? '0' : '-1');
            if (panel) panel.hidden = !on;
        });
    };

    tabs.forEach(function (tab, i) {
        tab.addEventListener('click', function (e) {
            e.preventDefault();
            select(tab);
        });
        tab.addEventListener('keydown', function (e) {
            if (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft') return;
            e.preventDefault();
            const next = tabs[(i + (e.key === 'ArrowRight' ? 1 : tabs.length - 1)) % tabs.length];
            next.focus();
            select(next);
        });
    });
}

// Pinned games: the visitor's own watch list. There is no account on this site,
// so the list lives in this browser, oldest pin first, and the cap drops the
// oldest when a seventh is placed. The price at pinning rides along so the sheet
// can report which way it has moved since.
const PIN_KEY = 'bggd.pins';
const PIN_MAX = 6;

function readPins() {
    try {
        const pins = JSON.parse(localStorage.getItem(PIN_KEY));
        return Array.isArray(pins) ? pins.filter(function (p) { return p && p.id; }) : [];
    } catch (e) {
        return [];
    }
}

function writePins(pins) {
    try {
        localStorage.setItem(PIN_KEY, JSON.stringify(pins));
    } catch (e) {
        // Storage denied or full: the pin simply does not persist.
    }
}

// The pin toggle on a game sheet.
function initPin() {
    const btn = document.getElementById('pin-btn');
    if (!btn) return;
    const id = parseInt(btn.dataset.game, 10);
    if (!id) return;

    const paint = function (on) {
        btn.setAttribute('aria-pressed', on ? 'true' : 'false');
        btn.querySelector('i').className = on ? 'bi bi-pin-angle-fill' : 'bi bi-pin-angle';
        btn.querySelector('.pin-label').textContent = on ? 'Pinned' : 'Pin';
    };

    const pinned = function () {
        return readPins().some(function (p) { return p.id === id; });
    };

    paint(pinned());

    btn.addEventListener('click', function () {
        const on = pinned();
        let pins = readPins().filter(function (p) { return p.id !== id; });
        if (!on) {
            pins.push({id: id, price: btn.dataset.price || '', at: Date.now()});
            pins = pins.slice(-PIN_MAX);
        }
        writePins(pins);
        paint(!on);
    });
}

// The pinned tray on the home sheet. The page itself is cached and shared, so
// the tray is fetched for whatever this browser holds.
function initPinnedTray() {
    const section = document.getElementById('pinned');
    if (!section) return;
    const pins = readPins();
    if (!pins.length) return;

    // Newest pin leads, each carrying the price it was pinned at.
    const query = pins
        .slice()
        .reverse()
        .map(function (p) { return p.id + ':' + (p.price || ''); })
        .join(',');

    fetch(section.dataset.src + '?pins=' + encodeURIComponent(query))
        .then(function (res) { return res.ok ? res.text() : ''; })
        .then(function (html) {
            if (!html.trim()) return;
            document.getElementById('pinned-slot').innerHTML = html;
            section.hidden = false;
        })
        .catch(function () {
            // No tray rather than a broken one.
        });
}

// Cover art is served from the shops and from BGG, so a URL can rot. A dead
// image becomes the same printed blank a missing one gets, never an empty box.
const ART_WRAPS = '.counter-art, .crt-art, .roster-art, .detail-counter, .linked-art';

document.addEventListener(
    'error',
    function (e) {
        const img = e.target;
        if (!img || img.tagName !== 'IMG') return;
        const wrap = img.closest(ART_WRAPS);
        if (!wrap) return;
        img.hidden = true;
        wrap.classList.add('art-missing');
    },
    true // 'error' does not bubble, so listen on the capture phase
);

let trimTraysTimer;
window.addEventListener('resize', function () {
    clearTimeout(trimTraysTimer);
    trimTraysTimer = setTimeout(trimTrays, 150);
});

document.addEventListener('DOMContentLoaded', function () {
    initNavToggle();
    initTabs();
    initPin();
    initPinnedTray();
    trimTrays();
});
