from __future__ import print_function

import sys
import threading
import time
import datetime
import getpass
import platform
import string
import subprocess
import logging
import traceback
import json
from collections import OrderedDict


__author__ = 'Erik Moqvist'
__version__ = '3.10.0'


_RUN_HEADER_FMT ="""
Name: {name}
Date: {date}
Node: {node}
User: {user}\
"""

_TEST_HEADER_FMT = """
---------------------------------------------------------------

Name: {name}
Description:

{description}

"""

_TEST_FOOTER_FMT = """
{name}: {result} in {duration}\
"""

_SUMMARY_FMT = """
---------------------- Test summary begin ----------------------

{summary}

Execution time: {execution_time}
Result: {result}

----------------------- Test summary end -----------------------
"""

_DIGRAPH_FMT = """\
digraph {name} {{
    {begin_id} [label="begin" shape=box];
    {end_id} [label="end" shape=box];

{nodes}

{deps}
}}
"""

LOGGER = logging.getLogger(__name__)


def configure_logging(filename=None):
    """Configure the logging module to write output to the console and a
    file. The file name is `filename` if `filename` is not None,
    otherwise the file name is ``systest_<date>.log``.

    The console log level is ``INFO``.

    The file log level is ``DEBUG``.

    """

    # Configure the logging module.
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    # Use the color formatter for console output.
    stdout_handler = logging.StreamHandler()
    stdout_handler.setFormatter(ColorFormatter())
    stdout_handler.setLevel(logging.INFO)
    root_logger.addHandler(stdout_handler)

    # Add a prefix to entries written to file.
    if not filename:
        filename = "systest"
    filename = "{}-{}.log".format(filename, _make_filename(str(datetime.datetime.now())))
    file_handler = logging.FileHandler(filename, "w")
    file_handler.setFormatter(logging.Formatter("%(asctime)s %(name)s %(levelname)s %(message)s"))
    root_logger.addHandler(file_handler)


def log_lines(text):
    """Create a log entry of each line in given text.

    """

    for line in text.splitlines():
        LOGGER.info(line)


def trim_docstring(docstring):
    if docstring is None or not docstring.strip():
        return ''

    # Remove leading and trailing whitespaces.
    docstring = docstring.strip()

    # Convert tabs to spaces (following the normal Python rules) and
    # split into a list of lines:
    lines = docstring.expandtabs().splitlines()

    # Determine minimum indentation (first line doesn't count):
    indent = None

    for line in lines[1:]:
        stripped = line.lstrip()

        if stripped:
            if indent is None:
                indent = len(line) - len(stripped)
            else:
                indent = min(indent, len(line) - len(stripped))

    # Remove indentation (first line is special):
    trimmed = [lines[0].strip()]

    if indent is not None:
        for line in lines[1:]:
            trimmed.append(line[indent:].rstrip())

    return '\n'.join(trimmed)

class ColorFormatter(logging.Formatter):
    """Adds color to the log entries.

    """

    def format(self, record):
        formatted = super(ColorFormatter, self).format(record)
        formatted = formatted.replace("PASSED", '\033[0;32mPASSED\033[0m')
        formatted = formatted.replace("FAILED", '\033[0;31mFAILED\033[0m')
        formatted = formatted.replace("SKIPPED", '\033[0;33mSKIPPED\033[0m')

        return formatted


class SequencerTestFailedError(Exception):
    pass


class SequencerTestSkippedError(Exception):
    pass


class TestCase(object):
    """Base class of a test case executed by the sequencer.

    """

    PASSED = "PASSED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"

    def __init__(self, name=None):
        if name is not None:
            self.name = name
        else:
            self.name = type(self).__name__
        self.result = None
        self.message = None
        self.sequencer = None
        self.execution_time = None
        self.finish_time = None
        self.parents = []
        self.start_parent = None

    def setup(self):
        """Called before run().

        """

        pass

    def teardown(self):
        """Called after run().

        """

        pass

    def run(self):
        """The test case logic. This function is called be the sequencer to
        execute the test case.

        A test case can either pass or fail. It fails if any exception
        is raised, otherwise it passes.

        """

        pass

    def dry_run(self):
        """Called by the sequencer for a dry run execution. Should return the
        estimated execution time of the test case.

        """

        return 0.0

    def assert_equal(self, first, second):
        """Raise an exception if ``first`` and ``second`` are not equal.

        """

        if first != second:
            filename, line, _, _ = traceback.extract_stack()[-2]

            raise SequencerTestFailedError(
                '{}:{}: {} is not equal to {}'.format(filename,
                                                      line,
                                                      repr(first),
                                                      repr(second)))

    def assert_not_equal(self, first, second):
        """Raise an exception if ``first`` and ``second`` are equal.

        """

        if first == second:
            filename, line, _, _ = traceback.extract_stack()[-2]

            raise SequencerTestFailedError(
                '{}:{}: {} is equal to {}'.format(filename,
                                                  line,
                                                  repr(first),
                                                  repr(second)))

    def assert_true(self, condition):
        """Raise an exception if given condition `condition` is false.

        """

        if not condition:
            filename, line, _, _ = traceback.extract_stack()[-2]

            raise SequencerTestFailedError('{}:{}: {} is not true'.format(filename,
                                                                          line,
                                                                          condition))

    def assert_false(self, condition):
        """Raise an exception if given condition `condition` is true.

        """

        if condition:
            filename, line, _, _ = traceback.extract_stack()[-2]

            raise SequencerTestFailedError('{}:{}: {} is not false'.format(filename,
                                                                           line,
                                                                           condition))

    def assert_in(self, member, container):
        """Raise an exception if given member `member` is not found in given
        container `container`.

        """

        if member not in container:
            filename, line, _, _ = traceback.extract_stack()[-2]

            raise SequencerTestFailedError(
                '{}:{}: {} not found in {}'.format(filename,
                                                   line,
                                                   repr(member),
                                                   repr(container)))

    def assert_not_in(self, member, container):
        """Raise an exception if given member `member` is found in given
        container `container`.

        """

        if member in container:
            filename, line, _, _ = traceback.extract_stack()[-2]

            raise SequencerTestFailedError(
                '{}:{}: {} found in {}'.format(filename,
                                               line,
                                               repr(member),
                                               repr(container)))

    def assert_is_none(self, obj):
        """Raise an exception if given object `obj` is not None.

        """

        if obj is not None:
            filename, line, _, _ = traceback.extract_stack()[-2]

            raise SequencerTestFailedError(
                '{}:{}: {} is not None'.format(filename,
                                               line,
                                               repr(obj)))

    def assert_is_not_none(self, obj):
        """Raise an exception if given object `obj` is None.

        """

        if obj is None:
            filename, line, _, _ = traceback.extract_stack()[-2]

            raise SequencerTestFailedError(
                '{}:{}: {} is None'.format(filename,
                                           line,
                                           repr(obj)))

    def assert_greater(self, first, second):
        """Raise an exception if ``first`` is not greater than ``second``.

        """

        if first <= second:
            filename, line, _, _ = traceback.extract_stack()[-2]

            raise SequencerTestFailedError(
                '{}:{}: {} is not greater than {}'.format(filename,
                                                          line,
                                                          repr(first),
                                                          repr(second)))

    def assert_greater_equal(self, first, second):
        """Raise an exception if ``first`` is not greater than or equal to
        ``second``.

        """

        if first < second:
            filename, line, _, _ = traceback.extract_stack()[-2]

            raise SequencerTestFailedError(
                '{}:{}: {} is not greater than or equal to {}'.format(filename,
                                                                      line,
                                                                      repr(first),
                                                                      repr(second)))

    def assert_less(self, first, second):
        """Raise an exception if ``first`` is not less than ``second``.

        """

        if first >= second:
            filename, line, _, _ = traceback.extract_stack()[-2]

            raise SequencerTestFailedError(
                '{}:{}: {} is not less than {}'.format(filename,
                                                       line,
                                                       repr(first),
                                                       repr(second)))

    def assert_less_equal(self, first, second):
        """Raise an exception if ``first`` is not less than or equal to
        ``second``.

        """

        if first > second:
            filename, line, _, _ = traceback.extract_stack()[-2]

            raise SequencerTestFailedError(
                '{}:{}: {} is not less than or equal to {}'.format(filename,
                                                                   line,
                                                                   repr(first),
                                                                   repr(second)))

    def assert_raises(self, expected_type, expected_message=None):
        """Raise an exception if no exception of given type `exception_type`
        is raised.

        """

        class AssertRaises(object):

            def __init__(self, expected_type, expected_message):
                self.expected_type = expected_type
                self.expected_message = expected_message
                self.exception = None

            def __enter__(self):
                return self

            def __exit__(self, exception_type, exception_value, tb):
                if exception_type is None:
                    filename, line, _, _ = traceback.extract_stack()[-2]

                    raise SequencerTestFailedError(
                        '{}:{}: {} not raised'.format(filename,
                                                      line,
                                                      self.expected_type.__name__))
                elif exception_type == self.expected_type:
                    # Python 2 and 3 compatibility.
                    try:
                        self.exception = exception_value.with_traceback(None)
                    except AttributeError:
                        self.exception = exception_value

                    if self.expected_message in [None, str(exception_value)]:
                        return True

        return AssertRaises(expected_type, expected_message)

    def assert_none(self, obj):
        """Raise an exception if given object `obj` is not None.

        """

        if obj is not None:
            filename, line, _, _ = traceback.extract_stack()[-2]

            raise SequencerTestFailedError(
                '{}:{}: {} is not None'.format(filename,
                                               line,
                                               repr(obj)))


class Sequencer(object):

    def __init__(self,
                 name,
                 testcase_filter=None,
                 testcase_skip_filter=None,
                 dry_run=False,
                 force_serial_execution=False):
        self.name = name
        self.dry_run = dry_run
        self.tests = None
        self.execution_time = 0.0
        self.testcase_filter = testcase_filter
        self.testcase_skip_filter = testcase_skip_filter
        self.force_serial_execution = force_serial_execution
        self.continue_on_failure = True
        self.run_failed = False

    def is_testcase_enabled(self, test):
        enabled = True

        if self.testcase_filter is not None:
            enabled = test.name in self.testcase_filter

        if enabled:
            if self.testcase_skip_filter is not None:
                enabled = test.name not in self.testcase_skip_filter

        return enabled

    def run(self, *tests, **kwargs):
        """Run given testcase(s).

        Test cases may be grouped into lists and tuples. All test
        cases in a list are executed in serial and all test cases in a
        tuple are executed in parallel. Lists and/or tuples may be
        used in multiple levels in the sequence.

        For example, the sequence below starts with test case
        Test1. When Test1 has been executed, Test2 and the list of
        Test3 and Test4 are executed in parallel. When both Test2 and
        the list of Test3 and Test4 has been executed, Test5 is
        executed. Then the sequence ends.

        .. code-block:: python

           [
               Test1(),
               (
                   Test2(),
                   [
                       Test3(),
                       Test4()
                   ]
               ),
               Test5()
           ]

        """

        # Print the header the first time the function is called.
        if self.tests is None:
            log_lines(_RUN_HEADER_FMT.format(name=self.name,
                                             date=datetime.datetime.now(),
                                             node=platform.node(),
                                             user=getpass.getuser()))
            self.tests = []

        self.continue_on_failure = kwargs.get('continue_on_failure', True)
        self.run_failed = False
        self.tests += list(tests)

        start_time = time.time()

        thread = _TestThread(list(tests), self)
        thread.start()
        thread.join()

        end_time = time.time()
        self.execution_time += (end_time - start_time)

        return self.summary_count()

    def summary_count(self):
        """Compile the test execution summary and return it as a string.

        """

        def test(test, passed, failed, skipped):
            if test.result == TestCase.PASSED:
                passed += 1
            elif test.result == TestCase.FAILED:
                failed += 1
            else:
                skipped += 1

            return passed, failed, skipped

        def sequential_tests(tests, passed, failed, skipped):
            for test in tests:
                passed, failed, skipped = recursivly(test, passed, failed, skipped)
            return passed, failed, skipped

        def parallel_tests(tests, passed, failed, skipped):
            for test in tests:
                passed, failed, skipped = recursivly(test, passed, failed, skipped)
            return passed, failed, skipped

        def recursivly(tests, passed, failed, skipped):
            if isinstance(tests, TestCase):
                return test(tests, passed, failed, skipped)
            elif isinstance(tests, list):
                return sequential_tests(tests, passed, failed, skipped)
            elif isinstance(tests, tuple):
                return parallel_tests(tests, passed, failed, skipped)
            else:
                raise ValueError("bad type {}".format(type(tests)))

        return recursivly(self.tests, 0, 0, 0)

    def summary(self):
        """Compile the test execution summary and return it as a string.

        """

        def test(test, indent):
            fmt = ' ' * indent + test.name + ': {result}{message}'

            if test.result:
                result = test.result
            else:
                result = TestCase.SKIPPED

            if test.message is None:
                message = ''
            else:
                message = ' ({})'.format(test.message)

            return [fmt.format(result=result, message=message)]

        def sequential_tests(tests, indent):
            return ['\n'.join([' ' * indent + '[',
                               ',\n'.join(_flatten([recursivly(test, indent + 4)
                                                    for test in tests])),
                               ' ' * indent + ']'])]

        def parallel_tests(tests, indent):
            return ['\n'.join([' ' * indent + '(',
                               ',\n'.join(_flatten([recursivly(test, indent + 4)
                                                    for test in tests])),
                               ' ' * indent + ')'])]

        def recursivly(tests, indent):
            if isinstance(tests, TestCase):
                return test(tests, indent)
            elif isinstance(tests, list):
                return sequential_tests(tests, indent)
            elif isinstance(tests, tuple):
                return parallel_tests(tests, indent)
            else:
                raise ValueError("bad type {}".format(type(tests)))

        summary = '\n'.join(recursivly(self.tests, 0))

        number_of_failed_tets = self.summary_count()[1]

        if number_of_failed_tets > 0:
            result = TestCase.FAILED
        else:
            result = TestCase.PASSED

        return _SUMMARY_FMT.format(summary=summary,
                                   execution_time=_human_time(self.execution_time),
                                   result=result)

    def summary_json(self):
        """Compile the test execution summary and return it as a JSON object.

        """

        def test(test):
            if test.result:
                result = test.result
                execution_time = _human_time(test.execution_time)
            else:
                result = TestCase.SKIPPED
                execution_time = None

            summary = {
                'name': test.name,
                'description': trim_docstring(test.__doc__).splitlines(),
                'result': result,
                'execution_time': execution_time
            }

            if test.message is not None:
                summary['message'] = test.message

            return summary

        def sequential_tests(tests, testcases):
            return [recursivly(test, testcases) for test in tests]

        def parallel_tests(tests, testcases):
            return [recursivly(test, testcases) for test in tests]

        def recursivly(tests, testcases):
            if isinstance(tests, TestCase):
                testcases.append(test(tests))
            elif isinstance(tests, list):
                sequential_tests(tests, testcases)
            elif isinstance(tests, tuple):
                parallel_tests(tests, testcases)
            else:
                raise ValueError("bad type {}".format(type(tests)))

        testcases = []
        recursivly(self.tests, testcases)

        return OrderedDict([
            ('name', self.name),
            ('date', str(datetime.datetime.now())),
            ('node', platform.node()),
            ('user', getpass.getuser()),
            ('testcases', testcases)
        ])

    def dot_digraph(self):
        """Create a graphviz dot digraph of given test sequence.

        The slowest execution path has bold edges.

        Use the program ``dot`` to create an image from the output of
        this function.

        ``dot -Tpng -Gdpi=200 -o mysequence.png mysequence.dot``

        """

        def get_start_parent(test):
            start_time = -1.0
            start_parent = None

            for parent in test.parents:
                if parent.finish_time > start_time:
                    start_time = parent.finish_time
                    start_parent = parent

            return start_parent

        def _test(parents, test):
            test.parents = parents

            if test.result:
                test.start_parent = get_start_parent(test)
                test.finish_time = test.start_parent.finish_time + test.execution_time
                return [test]
            else:
                # Ignore tests that were not executed.
                return parents

        def sequential_tests(parents, tests):
            for test in tests:
                parents = recursivly(parents, test)
            return parents

        def parallel_tests(parents, tests):
            return _flatten([recursivly(parents, test) for test in tests])

        def recursivly(parents, tests):
            if isinstance(tests, TestCase):
                return _test(parents, tests)
            elif isinstance(tests, list):
                return sequential_tests(parents, tests)
            elif isinstance(tests, tuple):
                return parallel_tests(parents, tests)
            else:
                raise ValueError("bad type: {}".format(type(tests)))

        class Edge(object):

            def __init__(self, parent, test, style):
                self.parent = parent
                self.test = test
                self.style = style

            def __str__(self):
                return ('    {parent_id} -> {test_id} [label="{parent_finish_time}"'
                        ', style="{style}"];').format(
                            parent_id=id(self.parent),
                            test_id=id(self.test),
                            parent_finish_time=_human_time(self.parent.finish_time),
                            style=self.style)

        def edge_name(parent, test):
            return '{}  ->  {}'.format(id(parent), id(test))

        def edges_recursivly(edges, test, style):
            # Take the slowest path first.
            for parent in sorted(test.parents, key=lambda p: p.finish_time, reverse=True):
                if edge_name(parent, test) in edges:
                    continue
                if (style == "bold") and (test.start_parent == parent):
                    edges[edge_name(parent, test)] = Edge(parent, test, "bold")
                    edges_recursivly(edges, parent, "bold")
                else:
                    edges[edge_name(parent, test)] = Edge(parent, test, "solid")
                    edges_recursivly(edges, parent, "solid")

        def deps_test(edges, test):
            if test.result:
                return [str(edges[edge_name(parent, test)])
                        for parent in test.parents]
            else:
                return []

        def deps_sequential_tests(edges, tests):
            return _flatten([deps_recursivly(edges, test) for test in tests])

        def deps_parallel_tests(edges, tests):
            return _flatten([deps_recursivly(edges, test) for test in tests])

        def deps_recursivly(edges, tests):
            if isinstance(tests, TestCase):
                return deps_test(edges, tests)
            elif isinstance(tests, list):
                return deps_sequential_tests(edges, tests)
            elif isinstance(tests, tuple):
                return deps_parallel_tests(edges, tests)
            else:
                raise ValueError("bad type: {}".format(type(tests)))

        def nodes_test(test):
            return ['    {} [label="{}"]'.format(id(test), test.name)]

        def nodes_sequential_tests(tests):
            return _flatten([nodes_recursivly(test) for test in tests])

        def nodes_parallel_tests(tests):
            return _flatten([nodes_recursivly(test) for test in tests])

        def nodes_recursivly(tests):
            if isinstance(tests, TestCase):
                return nodes_test(tests)
            elif isinstance(tests, list):
                return nodes_sequential_tests(tests)
            elif isinstance(tests, tuple):
                return nodes_parallel_tests(tests)
            else:
                raise ValueError("bad type: {}".format(type(tests)))

        # Create the begin test case node.
        begin = TestCase("begin")
        begin.result = TestCase.PASSED
        begin.finish_time = 0.0

        # Create the end test case node.
        end = TestCase("end")
        end.result = TestCase.PASSED
        end.execution_time = 0.0

        # Use begin as the parent of the first test case.
        parents = [begin]

        for test in self.tests + [end]:
            parents = recursivly(parents, test)

        # Bold edges in the slowest execution path.
        edges = {}
        edges_recursivly(edges, end, "bold")

        deps = []

        for test in [begin] + self.tests + [end]:
            deps += deps_recursivly(edges, test)

        nodes = []

        for test in self.tests:
            nodes += nodes_recursivly(test)

        return _DIGRAPH_FMT.format(name=_make_filename(self.name),
                                   begin_id=id(begin),
                                   end_id=id(end),
                                   nodes='\n'.join(nodes),
                                   deps='\n'.join(deps))

    def _report_json(self, basename):
        filename_json = basename + ".json"

        with open(filename_json, 'w') as fout:
            fout.write(json.dumps(self.summary_json(), indent=4))

    def _report_dot(self, basename):
        filename_dot = basename + ".dot"
        filename_png = basename + ".png"

        with open(filename_dot, "w") as fout:
            fout.write(self.dot_digraph())

        try:
            command = ["dot", "-Tpng", "-Gdpi=200", "-o", filename_png, filename_dot]
            subprocess.check_call(command)
        except subprocess.CalledProcessError:
            print("Unable to create image from dot file '{}' using command '{}'".format(
                filename_dot, ' '.join(command)))
        except OSError:
            print(("Unable to create image from dot file '{}'. Program 'dot' is not "
                   "installed.").format(filename_dot))

    def report(self):
        """Print a summary and create a dot graph image.

        """

        log_lines(self.summary())

        basename = _make_filename(self.name)

        self._report_json(basename)
        self._report_dot(basename)


def _make_filename(text):
    result = ""

    for char in text:
        if char in string.digits + string.ascii_letters + "._":
            result += char
        else:
            result += "_"

    return result


def _flatten(l):
    """Flatten given list ``l``.

    [[1], [2]] -> [1, 2]

    """

    return [item for sublist in l for item in sublist]


def _human_time(seconds):
    mins = int(seconds // 60)
    secs = int(seconds - 60 * mins)

    return "{}m {}s".format(mins, secs)


class _TestThread(threading.Thread):

    def __init__(self, test, sequencer):
        super(_TestThread, self).__init__()
        self.test = test
        self.sequencer = sequencer
        self.result = None

    def run(self):
        """Run the test, list of tests or parallel tests.

        """

        self.result = TestCase.FAILED

        try:
            self.run_tests(self.test)
            self.result = TestCase.PASSED
        except SequencerTestSkippedError:
            self.result = TestCase.SKIPPED
        except SequencerTestFailedError:
            pass

    def run_test(self, test):
        docstring = trim_docstring(test.__doc__)
        description_lines = ['    ' + line for line in docstring.splitlines()]
        description = '\n'.join(description_lines)

        log_lines(_TEST_HEADER_FMT.format(name=test.name,
                                          description=description))

        test.sequencer = self.sequencer
        result = TestCase.FAILED
        message = None

        # Run the test.
        try:
            if self.sequencer.dry_run:
                start_time = None
                execution_time = test.dry_run()
            else:
                start_time = time.time()

                try:
                    if self.sequencer.is_testcase_enabled(test):
                        if self.sequencer.continue_on_failure:
                            test.setup()

                            try:
                                test.run()
                            finally:
                                test.teardown()
                        else:
                            if not self.sequencer.run_failed:
                                test.setup()

                                try:
                                    test.run()
                                finally:
                                    test.teardown()
                            else:
                                raise SequencerTestSkippedError('Testcase skipped by failure.')
                    else:
                        raise SequencerTestSkippedError('Testcase disabled by filter.')
                except SequencerTestSkippedError as e:
                    LOGGER.info("testcase skipped: %s", e)
                    result = TestCase.SKIPPED
                    message = str(e)
                    raise
                except BaseException as e:
                    self.sequencer.run_failed = True

                    for entry in traceback.format_exception(*sys.exc_info()):
                        for line in entry.splitlines():
                            LOGGER.error(line.rstrip())

                    message = str(e)
                    raise

            result = TestCase.PASSED
        finally:
            finish_time = time.time()

            if start_time is not None:
                execution_time = (finish_time - start_time)

            log_lines(_TEST_FOOTER_FMT.format(name=test.name,
                                              result=result,
                                              duration=_human_time(execution_time)))

            test.result = result
            test.message = message
            test.execution_time = execution_time
            test.finish_time = finish_time

    def run_sequential_tests(self, tests):
        """Run all tests in the list in sequential order.

        """

        prev_test_failed = False

        for test in tests:
            if prev_test_failed:
                prev_test_failed = False
                if isinstance(test, list):
                    continue

            thread = _TestThread(test, self.sequencer)
            thread.start()
            thread.join()

            if thread.result == TestCase.FAILED:
                prev_test_failed = True
                self.result = thread.result

    def run_parallel_tests(self, tests):
        """Start each test in the tests tuple in a separate thread.

        """

        # run each test in a separate thread
        children = []

        for test in tests:
            thread = _TestThread(test, self.sequencer)
            thread.start()
            children.append(thread)

        # wait for all children to finish their execution
        for child in children:
            child.join()

        # raise an exception if at least one test failed
        for child in children:
            if child.result == TestCase.FAILED:
                raise SequencerTestFailedError(
                    "At least one of the parallel testcases failed.")

    def run_tests(self, tests):
        """Run the test(s).

        """

        if isinstance(tests, TestCase):
            self.run_test(tests)
        elif isinstance(tests, list):
            self.run_sequential_tests(tests)
        elif isinstance(tests, tuple):
            if self.sequencer.force_serial_execution:
                self.run_sequential_tests(tests)
            else:
                self.run_parallel_tests(tests)
