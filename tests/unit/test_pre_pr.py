"""Reports must describe a successful check of the current source, not stale work."""
import unittest

from scripts.pre_pr import database_coverage, report_error


class PrePRReportTests(unittest.TestCase):
    def test_matching_report_is_accepted_and_stale_or_failing_report_is_rejected(self):
        report = {'passed': True, 'fingerprint': 'source', 'head': 'commit', 'incomplete': []}
        self.assertIsNone(report_error(report, 'source', 'commit'))
        self.assertIsNotNone(report_error(report, 'changed', 'commit'))
        self.assertIsNotNone(report_error(report, 'source', 'new-commit'))
        self.assertIsNotNone(report_error({**report, 'passed': False}, 'source', 'commit'))
        self.assertIsNotNone(report_error([], 'source', 'commit'))

    def test_missing_database_is_explicit_and_strict_mode_rejects_it(self):
        gaps = database_coverage(None)
        self.assertTrue(gaps)
        report = {'passed': True, 'fingerprint': 'source', 'head': 'commit', 'incomplete': gaps}
        self.assertIsNone(report_error(report, 'source', 'commit'))
        self.assertIsNotNone(report_error(report, 'source', 'commit', require_database=True))

    def test_socket_does_not_claim_tcp_authentication_coverage(self):
        self.assertTrue(database_coverage('postgresql:///database?host=/tmp/test'))
        self.assertEqual(database_coverage('postgresql://tester@localhost/test'), [])
