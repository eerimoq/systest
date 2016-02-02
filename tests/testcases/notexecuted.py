from systest import TestCase


class NotExecutedTest(TestCase):
    """A test that is not executed.

    """

    count = 0

    def __init__(self, name):
        super(NotExecutedTest, self).__init__()
        self.name = "notexecuted_" + name

    def run(self):
        NotExecutedTest.count += 1
        raise
