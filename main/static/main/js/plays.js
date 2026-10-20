// Plays sync: the confirm card's button starts it, then the page asks the
// server for the collection and one BGG page of plays at a time. The server
// holds each fetched page while the page asks it to save the plays a chunk at
// a time, which drives the two meters. Cancel aborts the request in flight and
// stops the loop; saved plays are kept. Requests are strictly one at a time:
// every call is awaited before the next is made, and the username lookup and
// the confirm card's buttons are put away while a sync runs.
(() => {
    const panel = document.getElementById('plays-sync');
    if (!panel) return;

    const COLLECTION_TRIES = 5;
    const COLLECTION_WAIT_MS = 3000;
    const REDIRECT_MS = 900;
    // A breather for the server between chunk saves.
    const CHUNK_GAP_MS = 100;

    const maxPages = Number(panel.dataset.maxPages);
    const perPage = Number(panel.dataset.perPage);
    const turns = document.getElementById('plays-turns');
    const turnBoxes = [...turns.querySelectorAll('.turn')];
    const pagesVal = document.getElementById('plays-pages-val');
    const gauge = document.getElementById('plays-gauge');
    const gaugeFill = document.getElementById('plays-gauge-fill');
    const savedVal = document.getElementById('plays-saved-val');
    const status = document.getElementById('plays-status');
    const done = document.getElementById('plays-done');
    const resultLink = document.getElementById('plays-result-link');
    const cancelBtn = document.getElementById('plays-cancel');
    const userLbl = document.getElementById('plays-sync-user');
    const lookup = document.getElementById('plays-check');

    let controller = null;

    const lockLookup = (locked) => {
        lookup.querySelectorAll('input, button').forEach((el) => { el.disabled = locked; });
    };

    const say = (text, isError = false) => {
        status.textContent = text;
        status.classList.toggle('is-error', isError);
    };

    const wait = (ms, signal) => new Promise((resolve, reject) => {
        const timer = setTimeout(resolve, ms);
        signal.addEventListener('abort', () => {
            clearTimeout(timer);
            reject(new DOMException('Cancelled', 'AbortError'));
        }, {once: true});
    });

    const post = (url, data) => fetch(url, {
        method: 'POST',
        body: new URLSearchParams(data),
        headers: {'X-CSRFToken': panel.dataset.csrf},
        signal: controller.signal,
    });

    const failure = async (res) => {
        const body = await res.json().catch(() => ({}));
        return new Error(body.error || `The server answered ${res.status}.`);
    };

    const drawPages = (current, pages, finished) => {
        turnBoxes.forEach((box, i) => {
            const n = i + 1;
            box.classList.toggle('is-done', n <= finished);
            box.classList.toggle('is-now', n === current);
            box.classList.toggle('is-off', pages !== null && n > pages);
        });
        const of = pages === null ? maxPages : pages;
        pagesVal.textContent = `${finished} / ${of}`;
        turns.setAttribute('aria-valuemax', String(of));
        turns.setAttribute('aria-valuenow', String(finished));
    };

    const drawSaved = (saved, target) => {
        const share = target ? Math.min(saved / target, 1) : 1;
        gaugeFill.style.width = `${share * 100}%`;
        savedVal.textContent = target
            ? `${saved.toLocaleString()} / ${target.toLocaleString()}`
            : saved.toLocaleString();
        gauge.setAttribute('aria-valuemax', String(target || 1));
        gauge.setAttribute('aria-valuenow', String(saved));
    };

    const syncCollection = async (username, displayName) => {
        for (let attempt = 1; attempt <= COLLECTION_TRIES; attempt++) {
            const res = await post(panel.dataset.collectionUrl, {
                username, display_name: displayName,
            });
            if (!res.ok) throw await failure(res);
            const body = await res.json();
            if (body.status === 'done') return body.owned;
            say(`BGG is preparing the collection (try ${attempt} of ${COLLECTION_TRIES})…`);
            await wait(COLLECTION_WAIT_MS, controller.signal);
        }
        throw new Error('BGG is still preparing the collection. Try again in a minute.');
    };

    const postJson = async (url, data) => {
        const res = await post(url, data);
        if (!res.ok) throw await failure(res);
        return res.json();
    };

    // Fetches one BGG page on the server, then saves it a chunk per request,
    // handing each chunk's running totals to onChunk.
    const syncPage = async (username, page, onFetched, onChunk) => {
        onFetched(await postJson(panel.dataset.pageUrl, {username, page}));
        for (;;) {
            await wait(CHUNK_GAP_MS, controller.signal);
            const chunk = await postJson(panel.dataset.chunkUrl, {username, page});
            onChunk(chunk);
            if (chunk.finished) return chunk;
        }
    };

    const finish = (username, text) => {
        say(text);
        resultLink.href = panel.dataset.resultUrl.replace('__user__', encodeURIComponent(username));
        done.hidden = false;
        cancelBtn.hidden = true;
    };

    const run = async (username, displayName, startBtn) => {
        controller = new AbortController();
        // Sync and See results are put away until the sync stops.
        const acts = startBtn.closest('.plays-who-acts');
        startBtn.disabled = true;
        acts.hidden = true;
        lockLookup(true);
        panel.hidden = false;
        done.hidden = true;
        cancelBtn.hidden = false;
        turns.classList.remove('is-caught');
        gauge.classList.remove('is-caught');
        userLbl.textContent = displayName || username;
        drawPages(0, null, 0);
        drawSaved(0, 0);

        let saved = 0;
        let created = 0;
        let updated = 0;
        let finished = 0;
        try {
            say('Reading the collection…');
            const owned = await syncCollection(username, displayName);
            say(`${owned} owned games read. Fetching plays…`);

            let pages = null;
            let target = 0;
            let caughtUp = false;
            for (let page = 1; page <= (pages ?? maxPages); page++) {
                drawPages(page, pages, finished);
                say(`Fetching page ${page}…`);
                const before = saved;
                const result = await syncPage(username, page, (fetched) => {
                    pages = Math.min(fetched.total_pages, maxPages);
                    target = Math.min(fetched.total, maxPages * perPage);
                    drawPages(page, pages, finished);
                    say(`Page ${page} of ${pages}: saving ${fetched.size} plays…`);
                }, (chunk) => {
                    saved = before + chunk.done;
                    drawSaved(saved, target);
                });
                saved = before + result.done;
                created += result.created;
                updated += result.updated;
                finished = page;
                caughtUp = result.caught_up;
                drawSaved(saved, target);
                // A page where nothing was new or changed means the older pages are stored too.
                if (caughtUp) break;
            }

            const changes = `${created.toLocaleString()} new, ${updated.toLocaleString()} updated`;
            if (caughtUp) {
                // Everything older is already stored: the rest of the track is not needed.
                drawPages(0, finished, finished);
                turns.classList.add('is-caught');
                gauge.classList.add('is-caught');
                finish(username, `Caught up after page ${finished}: ${changes}.`);
            } else {
                drawPages(0, pages ?? 0, finished);
                const of = finished === 1 ? '1 page' : `${finished} pages`;
                finish(username, `Done: ${saved.toLocaleString()} plays read from ${of}, ${changes}.`);
            }
            setTimeout(() => { window.location.href = resultLink.href; }, REDIRECT_MS);
        } catch (err) {
            drawPages(0, null, finished);
            if (err.name === 'AbortError') {
                finish(username, saved
                    ? `Cancelled. The ${saved.toLocaleString()} plays read so far are kept.`
                    : 'Cancelled before any plays were saved.');
            } else {
                say(err.message, true);
                cancelBtn.hidden = true;
                if (saved) {
                    resultLink.href = panel.dataset.resultUrl
                        .replace('__user__', encodeURIComponent(username));
                    done.hidden = false;
                }
            }
        } finally {
            startBtn.disabled = false;
            acts.hidden = false;
            lockLookup(false);
        }
    };

    // The confirm card arrives by htmx, so its button is caught by delegation.
    document.addEventListener('click', (e) => {
        const startBtn = e.target.closest('#plays-start');
        if (!startBtn || startBtn.disabled) return;
        run(startBtn.dataset.username, startBtn.dataset.displayName, startBtn);
    });

    cancelBtn.addEventListener('click', () => {
        if (controller) controller.abort();
    });
})();
