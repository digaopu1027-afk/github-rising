"""One real, source-backed model request, for an explicit workflow smoke test.

Uses the Actions secret already available in the environment; prints no keys,
request headers, raw provider response, or chain of thought.
"""
import argparse
import json
import os
from pathlib import Path
from urllib.error import HTTPError

from .collect import ROOT, load, atomic_json, generate_content, now


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state-dir', default='.data')
    args = parser.parse_args()
    state = Path(args.state_dir)
    if not os.environ.get('LLM_API_KEY') or not os.environ.get('LLM_MODEL'):
        raise SystemExit('Configure LLM_API_KEY and LLM_MODEL before checking the model.')
    board = load(ROOT / 'public/data/latest.json')
    candidates = []
    for repo in board['projects']:
        material = load(state / 'materials' / (str(repo['id']) + '.json'), {})
        if material.get('available') and len(material.get('readme', '')) > 100:
            candidates.append((bool(repo.get('summary_zh')), len(material['readme']), repo, material))
    if not candidates:
        raise SystemExit('No source-backed project available for a model check.')
    _, _, repo, source = min(candidates, key=lambda value: value[:2])
    print('Testing model on one project: ' + repo['full_name'], flush=True)
    try:
        content = generate_content(repo, source)
        if content is None:
            raise ValueError('Model returned no validated content')
    except HTTPError as exc:
        # Provider bodies can contain credentials; report only the status code.
        raise SystemExit('Model request failed: HTTP %d. Check provider account access and model availability.' % exc.code)
    except Exception as exc:
        # Internal validation messages contain no excerpts or model output.
        if isinstance(exc, ValueError):
            message = str(exc)
            if os.environ['LLM_API_KEY'] in message:
                message = 'Provider response could not be validated'
            raise SystemExit('Model response rejected: ' + message)
        raise SystemExit('Model check failed: ' + type(exc).__name__)
    result = dict(content, material_hash=source['hash'], readme_url=source['readme_url'], content_status='generated')
    atomic_json(state / 'content' / (str(repo['id']) + '.json'), result)
    proof = {'checked_at': now(), 'model': os.environ['LLM_MODEL'], 'status': 'passed',
             'repository_id': repo['id'], 'full_name': repo['full_name'],
             'evidence_count': len(content['evidence']), 'summary_zh': content['summary_zh']}
    atomic_json(state / 'model-check.json', proof)
    print(json.dumps(proof, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
