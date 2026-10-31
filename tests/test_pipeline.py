import copy
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from collector.core import eligible, observe, build_rankings
from collector.collect import atomic_json, make_board, publish, export_all, validate_content, safe_url, collect, fetch_repo, ApiError

AT = datetime(2026, 10, 30, 1, tzinfo=timezone.utc)


def repo(id=1, stars=100, hours=0, **values):
    value = {'id': id, 'name': 'project', 'full_name': 'owner/project', 'stars': stars,
             'sampled_at': (AT + timedelta(hours=hours)).isoformat(),
             'visibility': 'public', 'fork': False, 'archived': False,
             'license': 'MIT', 'summary_zh': '真实用途'}
    value.update(values)
    return value


class RankingTests(unittest.TestCase):
    def test_first_observation_does_not_claim_growth(self):
        row = observe(repo(stars=100000), None)
        self.assertIsNone(row['delta'])
        self.assertEqual(build_rankings([row]), ([], []))

    def test_only_22_to_26_hour_comparisons_are_ranked(self):
        for hours, accepted in [(21.99, False), (22, True), (24, True), (26, True), (26.01, False), (48, False)]:
            with self.subTest(hours=hours):
                row = observe(repo(stars=150, hours=hours), repo())
                self.assertEqual(row['delta'] == 50, accepted)
                self.assertEqual(bool(build_rankings([row])[0]), accepted)

    def test_net_decrease_and_zero_stay_out_of_rankings(self):
        rows = [observe(repo(stars=n, hours=24), repo()) for n in (95, 100)]
        self.assertEqual(rows[0]['delta'], -5)
        self.assertEqual(build_rankings(rows), ([], []))

    def test_hot_ties_use_growth_then_fixed_id(self):
        rows = [observe(repo(id=id, stars=old + 20, hours=24), repo(id=id, stars=old))
                for id, old in [(3, 100), (2, 50), (1, 50)]]
        hot, _ = build_rankings(rows)
        self.assertEqual([r['id'] for r in hot], [1, 2, 3])

    def test_rising_thresholds_and_smoothed_baseline(self):
        rows = [observe(repo(id=i, stars=n, hours=24), repo(id=i, stars=n-d))
                for i, n, d in [(1, 50, 10), (2, 60, 9), (3, 5000, 10), (4, 5001, 100), (5, 120, 30), (6, 49, 30)]]
        _, rising = build_rankings(rows)
        self.assertEqual([r['id'] for r in rising], [5, 1, 3])

    def test_zero_baseline_does_not_generate_infinity(self):
        row = observe(repo(stars=50, hours=24), repo(stars=0))
        self.assertIsNone(row['growth_rate'])
        self.assertEqual(row['rising_score'], .5)
        json.dumps(row, allow_nan=False)

    def test_license_fork_private_and_archive_exclusions(self):
        self.assertTrue(eligible(repo(), {'MIT'}))
        for changes in [{'license': None}, {'license': 'NOASSERTION'}, {'license': 'BUSL-1.1'},
                        {'fork': True}, {'archived': True}, {'disabled': True}, {'visibility': 'private'}]:
            self.assertFalse(eligible(repo(**changes), {'MIT'}))

    def test_rank_limits(self):
        rows = [observe(repo(id=i, stars=100+i, hours=24), repo(id=i, stars=50)) for i in range(80)]
        hot, rising = build_rankings(rows)
        self.assertEqual((len(hot), len(rising)), (50, 20))
        self.assertEqual([r['rank'] for r in hot], list(range(1, 51)))

    def test_repository_rename_uses_id_not_name(self):
        previous = {'date': '2026-10-30', 'repos': {'1': repo()}}
        current = {'repos': {'1': repo(stars=160, hours=24, full_name='new-owner/new-name')}}
        board = make_board('2026-10-31', current, previous, [], [], 1, {'MIT'})
        self.assertEqual(len(board['projects']), 1)
        self.assertEqual(board['hot'][0]['delta'], 60)
        self.assertEqual(board['hot'][0]['full_name'], 'new-owner/new-name')

    def test_missing_repo_is_not_assumed_zero(self):
        previous = {'date': '2026-10-30', 'repos': {'1': repo(), '2': repo(id=2)}}
        current = {'repos': {'1': repo(stars=150, hours=24)}}
        board = make_board('2026-10-31', current, previous, [], [], 2, {'MIT'})
        self.assertEqual([p['id'] for p in board['projects']], [1])


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.state = Path(self.temp.name) / 'state'
        self.output = Path(self.temp.name) / 'public'

    def tearDown(self):
        self.temp.cleanup()

    def board(self, day, stars, previous=None, hours=0):
        snapshot = {'repos': {'1': repo(stars=stars, hours=hours)}}
        return make_board(day, snapshot, previous, [], [], 1, {'MIT'})

    def test_second_day_publication_keeps_first_day_copy_and_content(self):
        first = self.board('2026-10-30', 100)
        publish(self.state, self.output, first)
        frozen_path = self.output / 'history/2026-10-30.json'
        before = hashlib.sha256(frozen_path.read_bytes()).hexdigest()
        previous = {'date': '2026-10-30', 'repos': {'1': repo()}}
        second = self.board('2026-10-31', 160, previous, 24)
        second['projects'][0]['summary_zh'] = '今天的新介绍'
        publish(self.state, self.output, second)
        self.assertEqual(hashlib.sha256(frozen_path.read_bytes()).hexdigest(), before)
        self.assertEqual(json.loads(frozen_path.read_text())['projects'][0]['summary_zh'], '真实用途')
        self.assertEqual(json.loads((self.output / 'latest.json').read_text())['hot'][0]['delta'], 60)

    def test_duplicate_publication_refuses_to_change_archive(self):
        board = self.board('2026-10-30', 100)
        publish(self.state, self.output, board)
        with self.assertRaises(ValueError):
            publish(self.state, self.output, dict(board, notes=['changed']))

    def test_failed_status_preserves_latest_and_exports_failure(self):
        publish(self.state, self.output, self.board('2026-10-30', 100))
        before = (self.output / 'latest.json').read_bytes()
        atomic_json(self.state / 'status.json', {'state': 'failed', 'message': '采集失败'})
        export_all(self.state, self.output)
        self.assertEqual((self.output / 'latest.json').read_bytes(), before)
        self.assertEqual(json.loads((self.output / 'status.json').read_text())['state'], 'failed')

    def test_same_day_rerun_does_not_call_github_or_change_board(self):
        from argparse import Namespace
        board = self.board('2026-10-30', 100)
        publish(self.state, self.output, board)
        with patch('collector.collect.now', return_value='2026-10-30T02:00:00+00:00'), patch('collector.collect.GitHub') as api:
            collect(Namespace(state_dir=str(self.state), output_dir=str(self.output)))
            api.assert_not_called()

    def test_missing_state_cannot_restart_over_existing_public_history(self):
        from argparse import Namespace
        atomic_json(self.output / 'history/index.json', [{'date': '2026-10-30'}])
        with patch('collector.collect.GitHub') as api:
            with self.assertRaises(ApiError):
                collect(Namespace(state_dir=str(self.state), output_dir=str(self.output)))
            api.assert_not_called()


class ContentTests(unittest.TestCase):
    def test_repo_that_became_private_is_never_persisted(self):
        from unittest.mock import Mock
        api = Mock()
        api.get.return_value = {'id': 1, 'private': True}
        with self.assertRaises(ApiError):
            fetch_repo(api, {'id': 1})

    def test_only_supplied_exact_evidence_is_accepted(self):
        r = {'description': 'A browser for AI and automation', 'url': 'https://github.com/a/b'}
        source = {'readme': 'Use the browser to automate tasks.', 'readme_url': 'https://github.com/a/b#readme'}
        value = {'summary_zh': '浏览器自动化工具', 'audience_zh': '自动化开发者',
                 'evidence': [{'source': 'description', 'quote': r['description']}]}
        self.assertEqual(validate_content(value, r, source)['evidence'][0]['url'], r['url'])
        value['evidence'][0]['quote'] = 'This feature does not actually exist.'
        with self.assertRaises(ValueError): validate_content(value, r, source)

    def test_unsafe_external_urls_are_rejected(self):
        for value in ['javascript:alert(1)', '//example.com', 'https://user:secret@example.com', '', None]:
            self.assertIsNone(safe_url(value))
        self.assertEqual(safe_url('https://example.com/docs'), 'https://example.com/docs')


if __name__ == '__main__':
    unittest.main()
