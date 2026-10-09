"""Focused, dependency-free regression checks using temporary local Git repositories."""
from datetime import datetime, timedelta
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('garden_generator', HERE / 'generate.py')
garden = importlib.util.module_from_spec(spec)
spec.loader.exec_module(garden)


class GeneratorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root, self.remote = self.base / 'checkout', self.base / 'remote.git'
        self.root.mkdir()
        self.cmd('git', 'init', '--quiet', '--bare', '--initial-branch=main', str(self.remote))
        self.g('init', '--quiet', '--initial-branch=main')
        self.g('config', 'user.name', garden.NAME)
        self.g('config', 'user.email', garden.EMAIL)
        self.g('config', 'commit.gpgsign', 'false')
        (self.root / 'gardener').mkdir()
        (self.root / 'garden').mkdir()
        shutil.copyfile(HERE / 'config.json', self.root / 'gardener/config.json')
        (self.root / 'gardener/state.json').write_text(json.dumps({
            'version': 1, 'counter': 0, 'day': None, 'category': 'none', 'target': 0, 'completed': 0,
        }))
        (self.root / 'garden/current.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg"/>\n')
        self.g('add', '.')
        self.g('commit', '--quiet', '-m', 'test: initialize temporary garden')
        self.g('remote', 'add', 'origin', str(self.remote))
        self.g('push', '--quiet', 'origin', 'main')
        self.initial = self.g('rev-parse', 'HEAD')
        self.current = datetime.now(garden.ZONE)
        self.event = self.base / 'event.json'
        self.metadata = {'repository': {'full_name': garden.REPOSITORY, 'default_branch': 'main',
                         'fork': False, 'private': False, 'owner': {'login': garden.NAME}}}
        self.event.write_text(json.dumps(self.metadata))
        for context in (
            patch.object(garden, 'ALLOWED_REMOTES', {str(self.remote)}),
            patch.object(garden, 'now', return_value=self.current),
            patch.dict(os.environ, {'GITHUB_EVENT_PATH': str(self.event),
                                    'GITHUB_REF': 'refs/heads/main', 'GARDENER_TOKEN': ''}),
        ):
            context.start()
            self.addCleanup(context.stop)

    def cmd(self, *argv):
        return subprocess.check_output(argv, text=True, stderr=subprocess.PIPE).strip()

    def g(self, *args):
        return self.cmd('git', '-C', str(self.root), *args)

    def remote_head(self):
        return self.cmd('git', '--git-dir', str(self.remote), 'rev-parse', 'main')

    def run_day(self, count=3, dry_run=False):
        with patch.object(garden, 'selection', return_value=('moderate', count)):
            return garden.run(self.root, dry_run)

    def test_probability_boundaries_and_limits(self):
        config = garden.read_config(self.root)
        for roll, category, maximum in [(0, 'none', 0), (19.999, 'none', 0),
            (20, 'light', 2), (49.999, 'light', 2), (50, 'moderate', 5),
            (79.999, 'moderate', 5), (80, 'heavy', 9), (94.999, 'heavy', 9),
            (95, 'very_heavy', 14), (99.999, 'very_heavy', 14)]:
            with self.subTest(roll=roll), patch.object(garden.random, 'Random') as fake:
                fake.return_value.random.return_value = roll / 100
                fake.return_value.randint.side_effect = lambda low, high: high
                self.assertEqual(garden.selection(config, '2026-10-09'), (category, maximum))
        self.assertEqual(garden.selection(config, '2026-10-09'), garden.selection(config, '2026-10-09'))

    def test_multiple_nonempty_attributed_commits_and_same_day_rerun(self):
        result = self.run_day()
        self.assertEqual(result['status'], 'success')
        self.assertEqual(len(result['commits']), 3)
        self.assertEqual(self.remote_head(), result['commits'][-1])
        for sha in result['commits']:
            fields = self.g('show', '-s', '--format=%an%n%ae%n%cn%n%ce%n%aI', sha).splitlines()
            self.assertEqual(fields[:4], [garden.NAME, garden.EMAIL, garden.NAME, garden.EMAIL])
            self.assertTrue(fields[4].endswith('-07:00'))
            self.assertEqual(set(self.g('diff-tree', '--no-commit-id', '--name-only', '-r', sha).splitlines()), garden.GENERATED)
        again = self.run_day(14)
        self.assertEqual(again['status'], 'already_complete')
        self.assertEqual(again['target'], 3)
        self.assertEqual(again['commits'], [])
        self.assertEqual(self.g('rev-list', '--count', self.initial + '..HEAD'), '3')

    def test_dry_run_is_non_destructive(self):
        before = (self.root / 'gardener/state.json').read_bytes()
        with patch.object(garden, 'push_verified', side_effect=AssertionError('no push')):
            self.assertEqual(self.run_day(dry_run=True)['status'], 'preview')
        self.assertEqual(self.g('rev-parse', 'HEAD'), self.initial)
        self.assertEqual((self.root / 'gardener/state.json').read_bytes(), before)
        self.assertEqual(self.g('status', '--porcelain'), '')

    def test_zero_activity_makes_no_commit(self):
        for _ in range(2):
            self.assertEqual(self.run_day(0)['status'], 'no_activity')
        self.assertEqual(self.remote_head(), self.initial)
        self.assertEqual(self.g('status', '--porcelain'), '')

    def test_failed_push_leaves_local_commits_and_retry_does_not_duplicate(self):
        real_git = garden.git
        def fail_push(root, *args, **kwargs):
            if args[0] == 'push':
                return subprocess.CompletedProcess(args, 1, '', 'simulated network failure')
            return real_git(root, *args, **kwargs)
        with patch.object(garden, 'git', side_effect=fail_push), self.assertRaisesRegex(RuntimeError, 'Push not confirmed'):
            self.run_day()
        self.assertEqual(self.remote_head(), self.initial)
        local_head = self.g('rev-parse', 'HEAD')
        self.assertNotEqual(local_head, self.initial)
        result = self.run_day()
        self.assertEqual(result['commits'], [])
        self.assertEqual(len(result['recovered_commits']), 3)
        self.assertTrue(result['push']['confirmed'])
        self.assertEqual(self.remote_head(), local_head)

    def test_fresh_checkout_after_failed_push_regenerates_same_frames_once(self):
        with patch.object(garden, 'push_verified', side_effect=RuntimeError('offline')), self.assertRaises(RuntimeError):
            self.run_day()
        frame = (self.root / 'garden/current.svg').read_bytes()
        fresh = self.base / 'fresh'
        self.cmd('git', 'clone', '--quiet', str(self.remote), str(fresh))
        with patch.object(garden, 'selection', return_value=('moderate', 3)):
            result = garden.run(fresh)
            again = garden.run(fresh)
        self.assertEqual(len(result['commits']), 3)
        self.assertEqual(again['commits'], [])
        self.assertEqual(frame, (fresh / 'garden/current.svg').read_bytes())

    def test_partial_day_resumes_saved_target(self):
        state = garden.read_state(self.root)
        state.update(day=str(self.current.date()), counter=1, target=3, completed=1, category='moderate')
        (self.root / 'gardener/state.json').write_text(json.dumps(state))
        (self.root / 'garden/current.svg').write_text(garden.render(state['day'], 1))
        self.g('add', '.')
        self.g('commit', '--quiet', '-m', f'chore(garden): render frame 1 for {state["day"]} (1/3)')
        self.g('push', '--quiet', 'origin', 'main')
        result = self.run_day(14)
        self.assertEqual(result['target'], 3)
        self.assertEqual(len(result['commits']), 2)
        self.assertEqual(result['completed'], 3)

    def test_dirty_tree_wrong_remote_and_wrong_branch_stop(self):
        note = self.root / 'unrelated.txt'
        note.write_text('user work')
        with self.assertRaisesRegex(RuntimeError, 'dirty'):
            self.run_day()
        note.unlink()
        self.g('remote', 'set-url', 'origin', str(self.base / 'not-authorized.git'))
        with self.assertRaisesRegex(RuntimeError, 'exclusively authorized'):
            self.run_day()
        self.g('remote', 'set-url', 'origin', str(self.remote))
        self.g('switch', '--quiet', '-c', 'other')
        with self.assertRaisesRegex(RuntimeError, 'Only main'):
            self.run_day()
        self.assertEqual(self.remote_head(), self.initial)

    def test_fork_private_and_wrong_repository_stop(self):
        for field, value in [('fork', True), ('private', True), ('full_name', 'someone/else'), ('default_branch', 'other')]:
            with self.subTest(field=field):
                metadata = json.loads(json.dumps(self.metadata))
                metadata['repository'][field] = value
                self.event.write_text(json.dumps(metadata))
                with self.assertRaisesRegex(RuntimeError, 'eligibility'):
                    self.run_day()
                self.assertEqual(self.remote_head(), self.initial)

    def test_remote_advance_does_not_rewrite_history(self):
        other = self.base / 'other-checkout'
        self.cmd('git', 'clone', '--quiet', str(self.remote), str(other))
        self.cmd('git', '-C', str(other), 'config', 'user.name', 'Local fixture')
        self.cmd('git', '-C', str(other), 'config', 'user.email', 'fixture@example.test')
        (other / 'note.txt').write_text('concurrent edit')
        self.cmd('git', '-C', str(other), 'add', '.')
        self.cmd('git', '-C', str(other), '-c', 'commit.gpgsign=false', 'commit', '--quiet', '-m', 'test: concurrent fixture edit')
        self.cmd('git', '-C', str(other), 'push', '--quiet', 'origin', 'main')
        remote = self.remote_head()
        with self.assertRaisesRegex(RuntimeError, 'Remote advanced'):
            self.run_day()
        self.assertEqual(self.remote_head(), remote)
        self.assertEqual(self.g('rev-parse', 'HEAD'), self.initial)

    def test_midnight_stops_before_push_without_backdating(self):
        values = [self.current, self.current, self.current, self.current + timedelta(days=1)]
        with patch.object(garden, 'now', side_effect=values), self.assertRaisesRegex(RuntimeError, 'Date changed'):
            self.run_day()
        self.assertEqual(self.remote_head(), self.initial)
        self.assertEqual(self.g('rev-list', '--count', self.initial + '..HEAD'), '1')

    def test_invalid_config_and_state_fail_closed(self):
        config = garden.read_config(self.root)
        config['distribution'][-1]['max'] = 15
        (self.root / 'gardener/config.json').write_text(json.dumps(config))
        with self.assertRaisesRegex(ValueError, '14'):
            garden.read_config(self.root)
        state = garden.read_state(self.root)
        state.update(completed=5, target=3)
        (self.root / 'gardener/state.json').write_text(json.dumps(state))
        with self.assertRaisesRegex(ValueError, 'Invalid state'):
            garden.read_state(self.root)


if __name__ == '__main__':
    unittest.main()
