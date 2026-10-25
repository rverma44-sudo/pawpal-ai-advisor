#!/usr/bin/env python3
"""Render real SVG changes in one daily Git transaction; Python standard library only."""
import argparse
import base64
from datetime import date, datetime
import hashlib
import json
import os
from pathlib import Path
import random
import subprocess
import sys
from xml.etree import ElementTree
from zoneinfo import ZoneInfo

REPOSITORY = 'rverma44-sudo/pawpal-ai-advisor'
NAME, EMAIL = 'rverma44-sudo', 'rverma44@asu.edu'
ZONE = ZoneInfo('America/Phoenix')
ALLOWED_REMOTES = {
    'https://github.com/' + REPOSITORY + '.git',
    'https://github.com/' + REPOSITORY,
    'git@github.com:' + REPOSITORY + '.git',
}
GENERATED = {'gardener/state.json', 'garden/current.svg'}
COMMIT_SUBJECTS = (
    'generate a new tile mosaic',
    'refresh the garden color grid',
    'draw the next procedural pattern',
    'compose a new SVG mosaic',
    'render the next garden artwork',
    'refresh tile colors and corner shapes',
    'generate the next garden snapshot',
    'redraw the seeded mosaic',
)


def commit_message(state):
    subject = COMMIT_SUBJECTS[(state['counter'] - 1) % len(COMMIT_SUBJECTS)]
    return (f'chore(garden): {subject}; frame {state["counter"]} for {state["day"]} '
            f'({state["completed"]}/{state["target"]})')


def now():
    return datetime.now(ZONE)


def git(root, *args, check=True, authenticate=False):
    env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
    env.update(TZ='America/Phoenix', GIT_TERMINAL_PROMPT='0', GIT_OPTIONAL_LOCKS='0')
    token = env.pop('GARDENER_TOKEN', '')
    if authenticate and token:
        encoded = base64.b64encode(('x-access-token:' + token).encode()).decode()
        env.update(GIT_CONFIG_COUNT='1', GIT_CONFIG_KEY_0='http.https://github.com/.extraheader',
                   GIT_CONFIG_VALUE_0='AUTHORIZATION: basic ' + encoded)
    result = subprocess.run(['git', '-C', str(root), *args], env=env, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
    if check and result.returncode:
        # Avoid leaking credentials or arbitrary server diagnostics into public logs.
        raise RuntimeError(f'git {args[0]} failed (exit {result.returncode})')
    return result


def read_config(root):
    config = json.loads((root / 'gardener/config.json').read_text())
    if not isinstance(config.get('seed'), str) or not config['seed']:
        raise ValueError('A nonempty seed is required')
    distribution = config['distribution']
    if not isinstance(distribution, list) or not distribution:
        raise ValueError('distribution must be a nonempty list')
    for item in distribution:
        if (not isinstance(item['name'], str) or not item['name']
            or type(item['weight']) not in (int, float)
            or any(type(item[k]) is not int for k in ('min', 'max'))
            or not 0 <= item['weight'] <= 100 or not 0 <= item['min'] <= item['max'] <= 14):
            raise ValueError('Invalid distribution entry; commit limits are 0 through 14')
    if sum(item['weight'] for item in distribution) != 100:
        raise ValueError('Distribution weights must total 100')
    return config


def selection(config, day):
    digest = hashlib.sha256((config['seed'] + ':' + day).encode()).digest()
    rng = random.Random(int.from_bytes(digest, 'big'))
    roll, boundary = rng.random() * 100, 0
    for item in config['distribution']:
        boundary += item['weight']
        if roll < boundary:
            return item['name'], rng.randint(item['min'], item['max'])
    raise ValueError('Invalid probability distribution')


def read_state(root):
    state = json.loads((root / 'gardener/state.json').read_text())
    if (state['version'] != 1 or type(state['counter']) is not int or state['counter'] < 0
        or any(type(state[k]) is not int for k in ('target', 'completed'))
        or not 0 <= state['completed'] <= state['target'] <= 14
        or state['counter'] < state['completed'] or not isinstance(state['category'], str)):
        raise ValueError('Invalid state; never delete state to retry')
    if state['day'] is not None and date.fromisoformat(state['day']).isoformat() != state['day']:
        raise ValueError('Invalid state date')
    return state


def render(day, counter):
    rng = random.Random(hashlib.sha256(f'{day}:{counter}'.encode()).digest())
    colors = ['#2ecc71', '#3498db', '#9b59b6', '#f1c40f', '#e67e22', '#1abc9c']
    lines = ['<svg xmlns="http://www.w3.org/2000/svg" width="384" height="420" viewBox="0 0 384 420">',
             f'<title>Automated procedural garden: {day}, frame {counter}</title>',
             '<rect width="384" height="420" fill="#17202a"/>']
    for y in range(8):
        for x in range(8):
            lines.append(f'<rect x="{x * 44 + 18}" y="{y * 44 + 18}" width="40" height="40" '
                         f'rx="{rng.randint(0, 15)}" fill="{rng.choice(colors)}"/>')
    lines.extend([f'<text x="192" y="402" text-anchor="middle" fill="#ffffff" '
                  f'font-family="monospace">{day} / frame {counter}</text>', '</svg>'])
    svg = '\n'.join(lines) + '\n'
    ElementTree.fromstring(svg)  # Every generated frame must be valid XML.
    return svg


def check_checkout(root):
    if git(root, 'branch', '--show-current').stdout.strip() != 'main':
        raise RuntimeError('Only main is authorized')
    for flags in ((), ('--push',)):
        if git(root, 'remote', 'get-url', *flags, 'origin').stdout.strip() not in ALLOWED_REMOTES:
            raise RuntimeError('Remote is not the exclusively authorized repository')
    if git(root, 'status', '--porcelain', '--untracked-files=all').stdout:
        raise RuntimeError('Working tree was dirty; stopped before making changes')


def check_event():
    path = os.environ.get('GITHUB_EVENT_PATH')
    if not path:
        raise RuntimeError('Use GitHub Actions workflow_dispatch for real runs')
    repo = json.loads(Path(path).read_text())['repository']
    if (repo['full_name'] != REPOSITORY or repo['default_branch'] != 'main'
        or repo['fork'] or repo['private'] or repo['owner']['login'] != NAME
        or os.environ.get('GITHUB_REF') != 'refs/heads/main'):
        raise RuntimeError('Repository eligibility or default-branch identity changed')


def verify_owned_ahead(root):
    if git(root, 'merge-base', '--is-ancestor', 'FETCH_HEAD', 'HEAD', check=False).returncode:
        raise RuntimeError('Remote advanced; retry from a fresh main checkout, without rewriting history')
    shas = git(root, 'rev-list', '--reverse', 'FETCH_HEAD..HEAD').stdout.splitlines()
    for sha in shas:
        identity = git(root, 'show', '-s', '--format=%an%n%ae%n%cn%n%ce%n%s', sha).stdout.splitlines()
        files = set(git(root, 'diff-tree', '--no-commit-id', '--name-only', '-r', sha).stdout.splitlines())
        state = json.loads(git(root, 'show', f'{sha}:gardener/state.json').stdout)
        legacy_message = (f'chore(garden): render frame {state["counter"]} for {state["day"]} '
                          f'({state["completed"]}/{state["target"]})')
        if (identity[:4] != [NAME, EMAIL, NAME, EMAIL]
            or identity[4] not in {commit_message(state), legacy_message} or files != GENERATED):
            raise RuntimeError('Unpublished non-gardener commits exist; refusing to push them')
    return shas


def push_verified(root):
    head = git(root, 'rev-parse', 'HEAD').stdout.strip()
    result = git(root, 'push', '--porcelain', 'origin', 'HEAD:refs/heads/main',
                 check=False, authenticate=True)
    remote = git(root, 'ls-remote', 'origin', 'refs/heads/main', check=False)
    actual = remote.stdout.split()[0] if remote.returncode == 0 and remote.stdout.split() else None
    if actual != head:
        raise RuntimeError(f'Push not confirmed (exit {result.returncode}); local commits remain intact; '
                           'retry the workflow from fresh main, never force-push')
    return {'confirmed': True, 'remote_head': actual, 'push_exit_code': result.returncode}


def run(root, dry_run=False):
    check_checkout(root)
    config, state = read_config(root), read_state(root)
    day = now().date().isoformat()
    if state['day'] and state['day'] > day:
        raise RuntimeError('Clock moved backwards; refusing historical activity')
    category, target = (state['category'], state['target']) if state['day'] == day else selection(config, day)
    result = {'repository': REPOSITORY, 'day': day, 'category': category, 'target': target,
              'completed': state['completed'] if state['day'] == day else 0, 'commits': [],
              'timestamp': now().isoformat(), 'dry_run': dry_run}
    if dry_run:
        return {**result, 'status': 'preview'}
    check_event()
    git(root, 'fetch', '--quiet', 'origin', 'main')
    ahead = verify_owned_ahead(root)
    # A failed/uncertain previous push may have left local commits. Verify their
    # ownership and publish them before considering any further generation.
    if ahead:
        result['recovered_commits'] = ahead
        result['push'] = push_verified(root)
    if target == 0:
        return {**result, 'status': 'no_activity'}
    if state['day'] != day:
        state.update(day=day, category=category, target=target, completed=0)
    while state['completed'] < state['target']:
        if now().date().isoformat() != day:
            raise RuntimeError('Date changed mid-session; stopped without backdating')
        state['counter'] += 1
        state['completed'] += 1
        (root / 'garden/current.svg').write_text(render(day, state['counter']))
        (root / 'gardener/state.json').write_text(json.dumps(state, indent=2) + '\n')
        read_state(root)
        git(root, 'add', '--', *sorted(GENERATED))
        files = set(git(root, 'diff', '--cached', '--name-only').stdout.splitlines())
        if files != GENERATED:
            raise RuntimeError('Unexpected or empty generated changes; no commit created')
        git(root, '-c', f'user.name={NAME}', '-c', f'user.email={EMAIL}',
            '-c', 'commit.gpgsign=false', 'commit', '--quiet', '-m',
            commit_message(state))
        sha = git(root, 'rev-parse', 'HEAD').stdout.strip()
        result['commits'].append(sha)
        print(json.dumps({'event': 'commit_created', 'sha': sha, 'day': day, 'frame': state['counter']}), flush=True)
    if result['commits']:
        result['push'] = push_verified(root)
    result.update(completed=state['completed'], status='success' if result['commits'] or ahead else 'already_complete')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    try:
        result = run(root, args.dry_run)
        exit_code = 0
    except (RuntimeError, ValueError, KeyError, TypeError, OSError, subprocess.TimeoutExpired) as exc:
        result, exit_code = {'status': 'failed', 'error': str(exc), 'timestamp': now().isoformat()}, 1
    print(json.dumps(result, indent=2), flush=True)
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with Path(os.environ['GITHUB_STEP_SUMMARY']).open('a') as handle:
            handle.write('## Contribution Garden\n\n```json\n' + json.dumps(result, indent=2) + '\n```\n')
    return exit_code


if __name__ == '__main__':
    sys.exit(main())
