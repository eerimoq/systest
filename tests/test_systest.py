import unittest

from systest import Sequence, SequencerTestFailedError

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

        class MySequence(Sequence):
            
            def __init__(self):
                super(MySequence, self).__init__("serial_parallel")

            def run(self):
                # Run test a and b.
                self.sequencer.run(
                    NamedTest("a"),
                    NamedTest("b")
                )
        
                # Run a bunch of tests
                try:
                    self.sequencer.run([
                        # tests in a tuple are executed in parallel
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
                    self.sequencer.run(
                        NamedTest("k"),
                        NamedTest("l")
                    )

        # execute the sequence
        MySequence().execute()

        self.assertEqual(NamedTest.count, 12)
        self.assertEqual(NotExecutedTest.count, 0)
        self.assertEqual(FailTest.count, 3)

    def test_continue_on_failure(self):
        """Run all tests even if a test fails.

        """

        class MySequence(Sequence):

            def __init__(self):
                super(MySequence, self).__init__("continue_on_failure")

            def run(self):
                self.sequencer.run(
                    FailTest("1"),
                    NamedTest("a"),
                    [
                        FailTest("2"),
                        NamedTest("b")
                    ]
                )

        MySequence().execute(stop_on_failure=False)

        self.assertEqual(NamedTest.count, 2)
        self.assertEqual(NotExecutedTest.count, 0)
        self.assertEqual(FailTest.count, 2)

    def test_dot_digraph(self):
        """Create a dot digraph of given sequence.

        """

        class MySequence(Sequence):

            def __init__(self):
                super(MySequence, self).__init__("dot_digraph")

            def run(self):
                self.sequencer.run(
                    NamedTest("a"),
                    NamedTest("b")
                )
        
                self.sequencer.run([
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
                    NotExecutedTest("b")
                ])
        
                self.sequencer.run(
                    NamedTest("k"),
                    NamedTest("l")
                )

        MySequence().execute(dry_run=True, stop_on_failure=False)

    def test_sequence_test_filter(self):
        """Use the test execution filter to run a specific testcase in a
        sequence.

        """

        class MySequence(Sequence):

            def __init__(self):
                super(MySequence, self).__init__("filter")

            def run(self):
                self.sequencer.run(
                    FailTest("1"),
                    NamedTest("a"),
                    [
                        FailTest("2"),
                        NamedTest("b")
                    ]
                )

        MySequence().execute(["test_b"])

        self.assertEqual(NamedTest.count, 1)
        self.assertEqual(NotExecutedTest.count, 0)
        self.assertEqual(FailTest.count, 0)


if __name__ == '__main__':
    unittest.main()
