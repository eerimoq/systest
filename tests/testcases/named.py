from systest import TestCase, SequencerTestFailedError

import threading
import time
import logging

LOGGER = logging.getLogger(__name__)

class MyError(Exception):

    def __init__(self, foo, bar):
        super(MyError, self).__init__()
        self.foo = foo
        self.bar = bar

    def __str__(self):
        return self.foo + self.bar
    

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

        self.assert_true(True)
        self.assert_equal(False, False)

        with self.assert_raises(MyError, 'foobar') as cm:
            raise MyError('foo', 'bar')

        self.assert_equal(type(cm.exception), MyError)
        self.assert_equal(str(cm.exception), 'foobar')

        with self.assert_raises(RuntimeError):
            raise RuntimeError()

        try:
            with self.assert_raises(TypeError):
                raise RuntimeError()
        except RuntimeError:
            pass

    def dry_run(self):
        return self.work_time
