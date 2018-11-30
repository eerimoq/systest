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


class FailSetupTest(TestCase):
    """A test that always fails the setup.

    """

    count = 0

    def __init__(self, name):
        super(FailSetupTest, self).__init__()
        self.name = "fail_setup_" + name

    def setup(self):
        FailSetupTest.count += 1

        self.assert_in(1, [0, 2])


class FailTearDownTest(TestCase):
    """A test that always fails in teardown.

    """

    count = 0

    def __init__(self, name):
        super(FailTearDownTest, self).__init__()
        self.name = "fail_teardown_" + name

    def teardown(self):
        FailTearDownTest.count += 1

        self.assert_true(1 == 0)
