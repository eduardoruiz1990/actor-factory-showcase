"""Run one local Actor collection against a fake Greenhouse Job Board API; used by test_main in a fresh process.

The Apify SDK keeps its configuration and storage settings for the life of the
process, so every end-to-end test runs in its own interpreter, like a real run.
A board token 'acme-3' gets three jobs; 'blocked' is disallowed by robots.txt;
the directory lists 'team' and, without a matching job, 'other';
'team' has the jobs numbered in $TEAM_JOBS (default 1,2,3); 'flaky' has jobs 1
and 2 but answers HTTP 500 while $FLAKY_DOWN is set; any other token is an
unknown board (HTTP 404).
Usage: python -m tests.local_run '<settings json>'  -> prints {"pushed": n}
"""

import asyncio
import json
import os
import re
import sys

import httpx2
from apify import Actor

from my_actor import main as actor_main
from my_actor.polite import PoliteClient
from my_actor.source import Settings

CONTENT = '&lt;p&gt;Job {n}. Questions? Write to jobs@example.com&lt;/p&gt;'


def job(token: str, n: int) -> dict:
    return {
        'id': n, 'internal_job_id': 1000 + n, 'title': f'Engineer {n}', 'company_name': 'Acme',
        'location': {'name': 'Remote'}, 'absolute_url': f'https://boards.greenhouse.io/{token}/jobs/{n}',
        'updated_at': '2026-10-01T00:00:00-04:00', 'first_published': '2026-09-01T00:00:00-04:00',
        'requisition_id': f'R{n}', 'content': CONTENT.format(n=n),
        'departments': [{'id': 1, 'name': 'Engineering'}], 'offices': [{'id': 2, 'name': 'Remote'}],
    }


def api(request: httpx2.Request) -> httpx2.Response:
    if request.url.path == '/robots.txt':
        return httpx2.Response(200, text='User-agent: *\nDisallow: /v1/boards/blocked\n')
    if request.url.path.endswith('/records/index.json.gz'):
        return httpx2.Response(200, json={'boards': {
            'other': {'company': 'Other', 'jobs': [['Designer', 'Remote']]},
            'team': {'company': 'Acme', 'jobs': [['Engineer 1', 'Remote'], ['Engineer 2', 'Remote']]},
            'missing': {'company': 'Gone', 'jobs': [['Engineer 9', 'Remote']]}}})
    if request.url.path == '/v1/boards/team/jobs':
        numbers = [int(n) for n in os.environ.get('TEAM_JOBS', '1,2,3').split(',') if n]
        return httpx2.Response(200, json={'jobs': [job('team', n) for n in numbers], 'meta': {'total': len(numbers)}})
    if request.url.path == '/v1/boards/flaky/jobs':
        if os.environ.get('FLAKY_DOWN'):
            return httpx2.Response(500, text='Internal Server Error')
        return httpx2.Response(200, json={'jobs': [job('flaky', n) for n in (1, 2)], 'meta': {'total': 2}})
    match = re.fullmatch(r'/v1/boards/([^/]+)-(\d+)/jobs', request.url.path)
    if not match:
        return httpx2.Response(404, json={'status': 404, 'error': 'Job not found'})
    token, count = match.group(1), int(match.group(2))
    return httpx2.Response(200, json={'jobs': [job(token, n) for n in range(1, count + 1)], 'meta': {'total': count}})


async def _no_sleep(_seconds: float) -> None:
    return None


async def run(settings: Settings) -> int:
    http = PoliteClient(min_interval=0, transport=httpx2.MockTransport(api), sleep=_no_sleep)
    async with Actor(exit_process=False):
        pushed = await actor_main.collect(settings, http=http)
    await http.aclose()
    return pushed


if __name__ == '__main__':
    settings = Settings(**json.loads(sys.argv[1]))
    print(json.dumps({'pushed': asyncio.run(run(settings))}))
