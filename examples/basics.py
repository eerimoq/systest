#!/usr/bin/env python
#
# A simple example showcasing the basics.
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
        self.assert_true(1 == 1)
        self.assert_in(1, [1, 2])
        self.assert_none(None)

        with self.assert_raises(RuntimeError) as cm:
            raise RuntimeError('foo')

        self.assert_equal(str(cm.exception), 'foo')

# Configure the logging module.
systest.configure_logging()

sequencer = systest.Sequencer("my_sequence")

# Run the sequence.
sequencer.run([
        MyTestCase("1"),
        (
            MyTestCase("2"),
            [
                MyTestCase("3"),
                MyTestCase("4")
            ]
        ),
        MyTestCase("5")
    ])

# Print the report.
sequencer.report()
