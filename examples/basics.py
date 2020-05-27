#!/usr/bin/env python
#
# A simple example showcasing the basics of systest.
#

import logging
import systest

LOGGER = logging.getLogger(__name__)


# Define a testcase.
class MyTestCase(systest.TestCase):
    """Test case description.

    """

    def __init__(self, name):
        super(MyTestCase, self).__init__()
        self.name = "my_testcase_" + name

    def run(self):
        LOGGER.info("Hello!")

        self.assert_equal(1, 1)
        self.assert_not_equal(1, 2)
        self.assert_true(1 == 1)
        self.assert_false(1 == 2)
        self.assert_in(1, [1, 2])
        self.assert_not_in(1, [0, 2])
        self.assert_is_none(None)
        self.assert_is_not_none(1)
        self.assert_greater(2, 1)
        self.assert_greater_equal(2, 2)
        self.assert_less(1, 2)
        self.assert_less_equal(2, 2)

        with self.assert_raises(RuntimeError) as cm:
            raise RuntimeError('foo')

        self.assert_equal(str(cm.exception), 'foo')


systest.main("my_sequence",
             MyTestCase("1"),
             (
                 MyTestCase("2"),
                 [
                     MyTestCase("3"),
                     MyTestCase("4")
                 ]
             ),
             MyTestCase("5"))
