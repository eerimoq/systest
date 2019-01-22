import systest
from systest import TestCase
from systest import TestCaseSkippedError


class XFailPassedTest(TestCase):
    """A test that always xpasses.

    """

    @systest.xfail('Bug 1.')
    def run(self):
        pass


class XFailFailedTest(TestCase):
    """A test that always xfails.

    """

    @systest.xfail('Bug 2.')
    def run(self):
        raise Exception('Run failed!')


class XFailSkippedTest(TestCase):
    """A test that always skips.

    """

    @systest.xfail('Bug 3.')
    def run(self):
        raise TestCaseSkippedError('Skipped in xfail.')
