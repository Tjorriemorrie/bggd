"""Throwaway probe: run on the droplet to see what Amazon actually returns.

    python _amz_probe.py         # single request
    python _amz_probe.py 5       # 5 in a row

Writes everything to ./amz_probe_out.txt (botasaurus can swallow stdout).
Delete this file when done.
"""

import sys

print('probe: starting, importing botasaurus...', flush=True)

from botasaurus_requests import request as bot_request  # noqa: E402

print('probe: botasaurus imported', flush=True)

URL = (
    'https://www.amazon.co.za/s?i=toys&rh=n:28002628031,'
    'p_72:28056829031,p_6:A34KVLZUJN6MA,p_n_availability:28056815031&dc=&page=1'
)

MARKERS = [
    's-result-list',
    's-search-results',
    's-main-slot',
    'captcha',
    'not a robot',
    'automated access',
    'api-services-support',
    'Enter the characters',
    'To discuss automated',
    'Sorry, we just need',
    'Robot Check',
    'CAPTCHA',
]


def _log(fh, msg):
    print(msg, flush=True)
    fh.write(msg + '\n')
    fh.flush()


def main():
    """Fetch the Amazon search page and report what came back."""
    tries = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    with open('amz_probe_out.txt', 'w', encoding='utf-8') as out:
        for i in range(1, tries + 1):
            _log(out, f'--- try {i}/{tries} ---')
            try:
                res = bot_request.get(URL, headers={})
            except Exception as exc:  # noqa: BLE001
                _log(out, f'EXCEPTION: {exc!r}')
                continue
            text = res.text or ''
            _log(out, f'status : {res.status_code}')
            _log(out, f'len    : {len(text)}')
            _log(out, f'final  : {getattr(res, "url", "?")}')
            _log(out, f'server : {res.headers.get("server")}')
            _log(out, f'ctype  : {res.headers.get("content-type")}')
            for m in MARKERS:
                if m in text:
                    _log(out, f'marker : {m}')
            if i == tries:
                with open('amz_probe.html', 'w', encoding='utf-8') as fh:
                    fh.write(text)
                _log(out, 'wrote  : amz_probe.html')
                _log(out, f'head   : {text[:800]!r}')


if __name__ == '__main__':
    main()
    print('probe: done', flush=True)
