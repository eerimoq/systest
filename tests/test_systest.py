import unittest

import systest
from systest import Sequencer, SequencerTestFailedError, ColorFormatter

from tests.testcases.named import NamedTest
from tests.testcases.fail import FailTest
from tests.testcases.notexecuted import NotExecutedTest


class SysTestTest(unittest.TestCase):

    def setUp(self):
        NamedTest.count = 0
        NotExecutedTest.count = 0
        FailTest.count = 0

    def test_serial_parallel(self):
        """Run a sequence of serial and parallel tests.

        """

        sequencer = Sequencer("serial_parallel")

        # Run test a and b.
        sequencer.run(
            NamedTest("a"),
            NamedTest("b")
        )
        
        # Run a bunch of tests.
        try:
            sequencer.run([
                # Tests in a tuple are executed in parallel.
                (
                    NamedTest("c", work_time=0.2),
                    [
                        NamedTest("d"),
                        NamedTest("e"),
                        (
                            NamedTest("f"),
                            NamedTest("g")
                        ),
                        NamedTest("h"),
                        (
                            NamedTest("i", work_time=0.1),
                            NamedTest("j"),
                            FailTest("a")
                        ),
                        NotExecutedTest("a")
                    ],
                    FailTest("b"),
                    FailTest("c")
                ),
                NotExecutedTest("b")
            ])
            
            # sequencer.run() should throw the
            # SequencerTestFailedError exception since the test
            # FailTest() fails
            raise
            
        except SequencerTestFailedError:
            sequencer.run(
                NamedTest("k"),
                NamedTest("l")
            )

        sequencer.report()

        self.assertEqual(NamedTest.count, 12)
        self.assertEqual(NotExecutedTest.count, 0)
        self.assertEqual(FailTest.count, 3)

    def test_continue_on_failure(self):
        """Run all tests even if a test fails.

        """

        sequencer = Sequencer("continue_on_failure",
                              stop_on_failure=False)

        sequencer.run(
            FailTest("1"),
            NamedTest("a"),
            [
                FailTest("2"),
                NamedTest("b")
            ]
        )

        sequencer.report()

        self.assertEqual(NamedTest.count, 2)
        self.assertEqual(NotExecutedTest.count, 0)
        self.assertEqual(FailTest.count, 2)

    def test_dot_digraph(self):
        """Create a dot digraph of given sequence.

        """

        sequencer = Sequencer("dot_digraph",
                              dry_run=True,
                              stop_on_failure=False)

        sequencer.run(
            NamedTest("a"),
            NamedTest("b"),
            (
                NamedTest("c", work_time=0.2),
                [
                    NamedTest("d"),
                    NamedTest("e"),
                    (
                        NamedTest("f", work_time=1.4),
                        NamedTest("g")
                    ),
                    NamedTest("h"),
                    (
                        NamedTest("i", work_time=0.1),
                        NamedTest("j", work_time=3.2),
                        FailTest("a")
                    ),
                    NotExecutedTest("a")
                ],
                FailTest("b"),
                FailTest("c")
            ),
            NotExecutedTest("b"),
            NamedTest("k"),
            NamedTest("l")
        )

        sequencer.report()

    def test_testcase_filter(self):
        """Use the test execution filter to run a specific testcase in a
        sequence.

        """

        # A testcase in `testcase_skip_filter` will be skipped even if it is
        # in `testcase_filter`.
        sequencer = Sequencer("filter",
                              testcase_filter=["fail_1", "test_b"],
                              testcase_skip_filter=["fail_1"])

        sequencer.run(
            FailTest("1"),
            NamedTest("a"),
            [
                FailTest("2"),
                NamedTest("b")
            ]
        )

        sequencer.report()

        self.assertEqual(NamedTest.count, 1)
        self.assertEqual(NotExecutedTest.count, 0)
        self.assertEqual(FailTest.count, 0)

    def test_force_serial_execution(self):
        """Force serial test case execution.

        """

        sequencer = Sequencer("forced_serial_execution",
                              force_serial_execution=True)

        try:
            sequencer.run((
                FailTest("1"),
                NamedTest("a")
            ))
        except SequencerTestFailedError:
            pass
        
        sequencer.report()

        self.assertEqual(NamedTest.count, 0)
        self.assertEqual(NotExecutedTest.count, 0)
        self.assertEqual(FailTest.count, 1)


systest.configure_logging()

if __name__ == '__main__':
    unittest.main()
