import systest


class SkipTest(systest.TestCase):
    """A test that always skips.

    """

    count = 0

    def __init__(self, name, message):
        super(SkipTest, self).__init__()
        self.name = "skip_" + name
        self.message = message

    def run(self):
        SkipTest.count += 1

        raise systest.SequencerTestSkippedError(self.message)

