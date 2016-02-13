from systest import TestCase

import threading
import time
import logging

LOGGER = logging.getLogger(__name__)

class NamedTest(TestCase):
    """Named test printing it's value.

    """

    count = 0

    def __init__(self, name, work_time=0.0):
        super(NamedTest, self).__init__()
        self.name = "test_" + name
        self.work_time = work_time

    def run(self):
        NamedTest.count += 1
        time.sleep(self.work_time)
        LOGGER.debug("Named test(%s) run function called from thread %s.",
                     self.name,
                     threading.current_thread())

    def dry_run(self):
        return self.work_time
