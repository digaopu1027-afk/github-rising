"""Build an isolated UI fixture in a temp directory; never touch public/data.

python3 tests/build_fixture.py
All counts in this fixture are synthetic and must never be deployed.
"""
import copy
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from collector.collect import atomic_json, make_board, publish


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--failed', action='store_true', help='Render a failed update with the prior valid board')
    parser.add_argument('--stale', action='store_true', help='Render a record older than 30 hours')
    args = parser.parse_args()
    root = Path(tempfile.mkdtemp(prefix='github-rising-UI-TEST-'))
    public = root / 'public'
    public.mkdir()
    shutil.copy2(ROOT / 'public/favicon.svg', public / 'favicon.svg')
    seed = json.loads((ROOT / 'public/data/latest.json').read_text())['projects'][0]
    previous, current = {}, {}
    for i, (stars, gain, category) in enumerate([(120, 20, 'AI'), (1400, 400, '开发工具'), (80, 12, '设计创作')]):
        repo = copy.deepcopy(seed)
        repo.update(id=1000+i, full_name='UI-TEST/fixture-' + str(i), name='fixture-' + str(i),
                    description='Isolated UI test fixture, not a real public project.',
                    summary_zh='界面测试项目，数值为虚构夹具，不属于公开榜单。',
                    audience_zh='仅供开发验收，禁止发布。', category=category,
                    homepage=None, url='https://example.test/', readme_url='https://example.test/',
                    license='MIT', fork=False, archived=False, visibility='public', disabled=False,
                    evidence=[], content_status='editorial', stars=stars, sampled_at='2026-10-31T01:00:00+00:00')
        current[str(repo['id'])] = repo
        before = dict(repo, stars=stars-gain, sampled_at='2026-10-30T01:00:00+00:00')
        previous[str(repo['id'])] = before
    first = {'date': '2026-10-30', 'repos': previous}
    second = {'date': '2026-10-31', 'repos': current}
    state = root / 'state'
    atomic_json(state / 'status.json', {'state': 'partial', 'message': 'UI 测试夹具：数值为虚构，禁止发布。'})
    publish(state, public / 'data', make_board(first['date'], first, None, [], [], 3, {'MIT'}))
    publish(state, public / 'data', make_board(second['date'], second, first, [], [], 3, {'MIT'}))
    if args.failed:
        atomic_json(public / 'data/status.json', {'state': 'failed', 'attempted_at': '2026-10-31T03:00:00+00:00',
                    'message': 'UI 测试夹具：模拟采集失败，保留上一份记录。禁止发布。'})
    if args.stale:
        latest_path = public / 'data/latest.json'
        latest = json.loads(latest_path.read_text())
        latest['generated_at'] = '2020-01-01T00:00:00+00:00'
        atomic_json(latest_path, latest)
    env = dict(os.environ, PUBLIC_DIR=str(public), BASE_PATH='/')
    subprocess.run([str(ROOT / 'node_modules/.bin/astro'), 'build', '--outDir', str(root / 'dist')],
                   cwd=ROOT, env=env, check=True, stdout=subprocess.DEVNULL)
    print(root / 'dist')


if __name__ == '__main__':
    main()
