from systest import TestCase


class FailTest(TestCase):
    """A test that always fails.

    """

    count = 0

    def __init__(self, name):
        super(FailTest, self).__init__()
        self.name = "fail_" + name

    def run(self):
        FailTest.count += 1

        self.assert_equal(1, 0)
