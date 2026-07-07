"""Throwaway: check the botasaurus bridge itself, independent of Amazon.

    python -m main.shops._amz_bridge_check

Hits a couple of neutral endpoints so you can tell a bridge/egress problem
apart from an Amazon-specific block. Delete this file when done.
"""

from botasaurus_requests import request as bot_request

TARGETS = [
    'https://httpbin.org/ip',  # what IP does Amazon actually see?
    'https://httpbin.org/user-agent',  # what UA is the bridge sending?
    'https://www.amazon.co.za/',  # does the bare homepage load at all?
]


def main():
    """Probe neutral endpoints to isolate bridge vs. Amazon block."""
    for url in TARGETS:
        try:
            res = bot_request.get(url, headers={})
            body = (res.text or '')[:300]
            print(f'{res.status_code}  {len(res.text or "")}  {url}')
            print('   ', repr(body))
        except Exception as exc:  # noqa: BLE001
            print(f'ERR  {url}: {exc!r}')


if __name__ == '__main__':
    main()
