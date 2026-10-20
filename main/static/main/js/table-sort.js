// Sorts a table marked data-sortable in the browser. A header's button sorts its
// column ascending, and a second click descending. Each cell carries its key in
// data-sort, compared as numbers when the header has data-sort-type="num". A cell
// with an empty key sinks to the bottom either way, and equal keys keep their
// order, so ties stay in rank order.
(() => {
    document.querySelectorAll('table[data-sortable]').forEach((table) => {
        const body = table.tBodies[0];
        const heads = [...table.tHead.rows[0].cells];

        const compare = (a, b, numeric) => {
            if (!numeric) return a.localeCompare(b);
            const x = Number(a);
            const y = Number(b);
            return x === y ? 0 : x < y ? -1 : 1;
        };

        heads.forEach((th, col) => {
            const button = th.querySelector('button');
            if (!button) return;
            button.addEventListener('click', () => {
                const dir = th.getAttribute('aria-sort') === 'ascending' ? -1 : 1;
                heads.forEach((head) => {
                    head.removeAttribute('aria-sort');
                    head.classList.remove('asc', 'desc');
                });
                th.setAttribute('aria-sort', dir > 0 ? 'ascending' : 'descending');
                th.classList.add(dir > 0 ? 'asc' : 'desc');

                const numeric = th.dataset.sortType === 'num';
                const key = (row) => row.cells[col].dataset.sort || '';
                const rows = [...body.rows].sort((a, b) => {
                    const ka = key(a);
                    const kb = key(b);
                    if (!ka || !kb) return !ka - !kb;
                    return dir * compare(ka, kb, numeric);
                });
                body.append(...rows);
            });
        });
    });
})();
