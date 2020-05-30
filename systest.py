import re
import argparse
import difflib
import sys
import os
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
from collections import OrderedDict as odict
from humanfriendly import format_timespan


__author__ = 'Erik Moqvist'
__version__ = '5.12.0'


_RUN_HEADER_FMT ='''
Name: {name}
Date: {date}
Node: {node}
User: {user}\
'''

_TEST_HEADER_FMT = '''
---------------------------------------------------------------

Name: {name}
Description:

{description}

'''

_TEST_FOOTER_FMT = '''
{name}: {result} in {duration}\
'''

_SUMMARY_FMT = '''
---------------------- Test summary begin ----------------------

{summary}

Execution time: {execution_time}
Result: {result}

----------------------- Test summary end -----------------------
'''

_DIGRAPH_FMT = '''\
digraph {name} {{
    {begin_id} [label="begin" shape=box];
    {end_id} [label="end" shape=box];

{nodes}

{deps}
}}
'''

LOGGER = logging.getLogger(__name__)


def configure_logging(filename=None,
                      console_log_level=None,
                      file_log_level=None):
    """Configure the logging module to write output to the console and a
    file. The file name is `filename-<date>.log` if `filename` is not
    None, otherwise the file name is ``systest-<date>.log``.

    Use `console_log_level` to set the console log level. It is
    ``INFO`` by default.

    Use `file_log_level` to set the file log level. It is ``DEBUG`` by
    default.

    """

    if console_log_level is None:
        console_log_level = logging.INFO

    if file_log_level is None:
        file_log_level = logging.DEBUG

    # Configure the logging module.
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    # Use the color formatter for console output.
    stdout_handler = logging.StreamHandler()
    stdout_handler.setFormatter(ColorFormatter())
    stdout_handler.setLevel(console_log_level)
    root_logger.addHandler(stdout_handler)

    # Add a prefix to entries written to file.
    if not filename:
        filename = "systest"

    filename = f"{filename}-{_make_filename(str(datetime.datetime.now()))}.log"

    # Create any missing parent log file folders.
    dirname = os.path.dirname(filename)

    if dirname:
        if not os.path.exists(dirname):
            os.makedirs(dirname)

    file_handler = logging.FileHandler(filename, "w")
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s %(name)s %(levelname)s %(message)s"))
    file_handler.setLevel(file_log_level)
    root_logger.addHandler(file_handler)


def log_lines(text):
    """Create a log infi entry of each line in given text.

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


def xfail(message=None):
    """Expected failure run() decorator.

    """

    def wrap(func):
        def wrapper(*args, **kwargs):
            try:
                func(*args, **kwargs)
            except TestCaseSkippedError:
                raise
            except Exception:
                _log_traceback()

                raise TestCaseXFailedError(message)

            raise TestCaseXPassedError(message)

        return wrapper

    return wrap


class ColorFormatter(logging.Formatter):
    """Adds color to the log entries.

    """

    def format(self, record):
        formatted = super(ColorFormatter, self).format(record)
        formatted = formatted.replace(" PASSED", ' \033[0;32mPASSED\033[0m')
        formatted = formatted.replace(" FAILED", ' \033[0;31mFAILED\033[0m')
        formatted = formatted.replace(" SKIPPED", ' \033[0;33mSKIPPED\033[0m')
        formatted = formatted.replace(" XPASSED", ' \033[0;36mXPASSED\033[0m')
        formatted = formatted.replace(" XFAILED", ' \033[0;36mXFAILED\033[0m')

        return formatted


class TestCaseFailedError(Exception):
    pass


class TestCaseSkippedError(Exception):
    pass


class TestCaseXPassedError(Exception):
    pass


class TestCaseXFailedError(Exception):
    pass


class TestCase(object):
    """Base class of a test case executed by the sequencer.

    """

    PASSED = "PASSED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    XPASSED = "XPASSED"
    XFAILED = "XFAILED"

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

            raise TestCaseFailedError(
                f'{filename}:{line}: {first!r} is not equal to {second!r}')

    def assert_not_equal(self, first, second):
        """Raise an exception if ``first`` and ``second`` are equal.

        """

        if first == second:
            filename, line, _, _ = traceback.extract_stack()[-2]

            raise TestCaseFailedError(
                f'{filename}:{line}: {first!r} is equal to {second!r}')

    def assert_text_equal(self, first, second):
        """Raises an exception if ``first`` and ``second`` are not equal.

        This is equivalent to ``assert_equal`` except it requires the
        arguments to be multi-line strings. The description of the
        failure is presented in the exception as a diff. This is an
        easier way to determine what has gone wrong in multi-line
        text.

        """

        if first != second:
            filename, line, _, _ = traceback.extract_stack()[-2]
            differ = difflib.Differ()
            diff = differ.compare(first.splitlines(), second.splitlines())
            text = '\n'.join([diffline.rstrip('\n') for diffline in diff])

            raise TestCaseFailedError(f'{filename}:{line}: Mismatch found:\n{text}')

    def assert_true(self, condition):
        """Raise an exception if given condition `condition` is false.

        """

        if not condition:
            filename, line, _, _ = traceback.extract_stack()[-2]

            raise TestCaseFailedError(f'{filename}:{line}: {condition} is not true')

    def assert_false(self, condition):
        """Raise an exception if given condition `condition` is true.

        """

        if condition:
            filename, line, _, _ = traceback.extract_stack()[-2]

            raise TestCaseFailedError(f'{filename}:{line}: {condition} is not false')

    def assert_in(self, member, container):
        """Raise an exception if given member `member` is not found in given
        container `container`.

        """

        if member not in container:
            filename, line, _, _ = traceback.extract_stack()[-2]

            raise TestCaseFailedError(
                f'{filename}:{line}: {member!r} not found in {container!r}')

    def assert_not_in(self, member, container):
        """Raise an exception if given member `member` is found in given
        container `container`.

        """

        if member in container:
            filename, line, _, _ = traceback.extract_stack()[-2]

            raise TestCaseFailedError(
                f'{filename}:{line}: {member!r} found in {container!r}')

    def assert_is_none(self, obj):
        """Raise an exception if given object `obj` is not None.

        """

        if obj is not None:
            filename, line, _, _ = traceback.extract_stack()[-2]

            raise TestCaseFailedError(f'{filename}:{line}: {obj!r} is not None')

    def assert_is_not_none(self, obj):
        """Raise an exception if given object `obj` is None.

        """

        if obj is None:
            filename, line, _, _ = traceback.extract_stack()[-2]

            raise TestCaseFailedError(f'{filename}:{line}: {obj!r} is None')

    def assert_greater(self, first, second):
        """Raise an exception if ``first`` is not greater than ``second``.

        """

        if first <= second:
            filename, line, _, _ = traceback.extract_stack()[-2]

            raise TestCaseFailedError(
                f'{filename}:{line}: {first!r} is not greater than {second!r}')

    def assert_greater_equal(self, first, second):
        """Raise an exception if ``first`` is not greater than or equal to
        ``second``.

        """

        if first < second:
            filename, line, _, _ = traceback.extract_stack()[-2]

            raise TestCaseFailedError(
                f'{filename}:{line}: {first!r} is not greater than or equal to '
                f'{second!r}')

    def assert_less(self, first, second):
        """Raise an exception if ``first`` is not less than ``second``.

        """

        if first >= second:
            filename, line, _, _ = traceback.extract_stack()[-2]

            raise TestCaseFailedError(
                f'{filename}:{line}: {first!r} is not less than {second!r}')

    def assert_less_equal(self, first, second):
        """Raise an exception if ``first`` is not less than or equal to
        ``second``.

        """

        if first > second:
            filename, line, _, _ = traceback.extract_stack()[-2]

            raise TestCaseFailedError(
                f'{filename}:{line}: {first!r} is not less than or equal to '
                f'{second!r}')

    def assert_raises(self, expected_type, expected_message=None):
        """Raise an exception if no exception of given type(s) or subclass of
        given type(s) `expected_type` is raised.

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

                    try:
                        name = self.expected_type.__name__
                    except AttributeError:
                        name = ' or '.join([
                            expected_type.__name__
                            for expected_type in self.expected_type
                        ])

                    raise TestCaseFailedError(
                        f'{filename}:{line}: {name} not raised')
                elif issubclass(exception_type, self.expected_type):
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

            raise TestCaseFailedError(f'{filename}:{line}: {obj!r} is not None')


class Result(object):

    def __init__(self, passed=0, failed=0, skipped=0, xpassed=0, xfailed=0, total=0):
        self.passed = passed
        self.failed = failed
        self.skipped = skipped
        self.xpassed = xpassed
        self.xfailed = xfailed
        self.total = total

    def __getitem__(self, index):
        # Deprecated.
        if index == 0:
            return self.passed
        elif index == 1:
            return self.failed
        elif index == 2:
            return self.skipped
        else:
            raise IndexError

    def __iter__(self):
        # Deprecated.
        # Allows unpacking as ``passed, failed, skipped = result``.
        yield self.passed
        yield self.failed
        yield self.skipped

    def __str__(self):
        details = []

        if self.passed > 0:
            details.append(f'{self.passed} passed')

        if self.failed > 0:
            details.append(f'{self.failed} failed')

        if self.skipped > 0:
            details.append(f'{self.skipped} skipped')

        if self.xpassed > 0:
            details.append(f'{self.xpassed} xpassed')

        if self.xfailed > 0:
            details.append(f'{self.xfailed} xfailed')

        details.append(f'{self.total} total')

        if self.failed > 0:
            result = TestCase.FAILED
        else:
            result = TestCase.PASSED

        return f"{result} ({', '.join(details)})"


class Sequencer(object):

    def __init__(self,
                 name,
                 testcase_pattern=None,
                 dry_run=False,
                 force_serial_execution=False):
        self.name = name
        self.dry_run = dry_run
        self.tests = None
        self.execution_time = 0.0
        self.testcase_pattern = testcase_pattern
        self.force_serial_execution = force_serial_execution
        self.continue_on_failure = True
        self.run_failed = False

    def is_testcase_enabled(self, test):

        if self.testcase_pattern is None:
            enabled = True
        else:
            enabled = bool(re.search(self.testcase_pattern, test.name))

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

        def test(test, result):
            if test.result == TestCase.PASSED:
                result.passed += 1
            elif test.result == TestCase.FAILED:
                result.failed += 1
            elif test.result == TestCase.XPASSED:
                result.xpassed += 1
            elif test.result == TestCase.XFAILED:
                result.xfailed += 1
            else:
                result.skipped += 1

            result.total += 1

            return result

        def sequential_tests(tests, result):
            for test in tests:
                result = recursivly(test, result)

            return result

        def parallel_tests(tests, result):
            for test in tests:
                result = recursivly(test, result)

            return result

        def recursivly(tests, result):
            if isinstance(tests, TestCase):
                return test(tests, result)
            elif isinstance(tests, list):
                return sequential_tests(tests, result)
            elif isinstance(tests, tuple):
                return parallel_tests(tests, result)
            else:
                raise ValueError(f'bad type {type(tests)}')

        return recursivly(self.tests, Result())

    def summary_test(self, test, indent):
        """Returns a test case summary line.

        """

        fmt = ' ' * indent + test.name + ': {result}{duration}{message}'

        if test.result:
            result = test.result
        else:
            result = TestCase.SKIPPED

        if test.message is None:
            message = ''
        else:
            message = f' ({test.message})'

        if test.execution_time is None:
            duration = ''
        else:
            duration = f' in {format_timespan(test.execution_time)}'

        return fmt.format(result=result, duration=duration, message=message)

    def summary(self):
        """Compile the test execution summary and return it as a string.

        """

        def test(test, indent):
            return [self.summary_test(test, indent)]

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
                raise ValueError(f'bad type {type(tests)}')

        summary = '\n'.join(recursivly(self.tests, 0))

        result = self.summary_count()

        return _SUMMARY_FMT.format(summary=summary,
                                   execution_time=format_timespan(self.execution_time),
                                   result=result)

    def summary_json_test(self, test):
        """Returns a test case summary ordered dictionary.

        """

        if test.result:
            result = test.result
            execution_time = format_timespan(test.execution_time)
        else:
            result = TestCase.SKIPPED
            execution_time = None

        summary = odict([
            ('name', test.name),
            ('description', trim_docstring(test.__doc__).splitlines()),
            ('result', result),
            ('execution_time', execution_time)
        ])

        if test.message is not None:
            summary['message'] = test.message

        return summary

    def summary_json(self):
        """Compile the test execution summary and return it as a JSON object.

        """

        def test(test):
            return self.summary_json_test(test)

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
                raise ValueError(f'bad type {type(tests)}')

        testcases = []
        recursivly(self.tests, testcases)

        return odict([
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
                raise ValueError(f'bad type {type(tests)}')

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
                            parent_finish_time=format_timespan(self.parent.finish_time),
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
                raise ValueError(f'bad type {type(tests)}')

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
                raise ValueError(f'bad type {type(tests)}')

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
            print(f"Unable to create image from dot file '{filename_dot}' using "
                  f"command '{' '.join(command)}'")
        except OSError:
            print((f"Unable to create image from dot file '{filename_dot}'. Program "
                   f"'dot' is not installed."))

    def report(self):
        """Print a summary and create a dot graph image.

        """

        log_lines(self.summary())

        basename = _make_filename(self.name)

        self._report_json(basename)
        self._report_dot(basename)

    def report_and_exit(self):
        self.report()

        if self.run_failed:
            exit_code = 1
        else:
            exit_code = 0

        sys.exit(exit_code)


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
        except TestCaseSkippedError:
            self.result = TestCase.SKIPPED
        except TestCaseXPassedError:
            self.result = TestCase.XPASSED
        except TestCaseXFailedError:
            self.result = TestCase.XFAILED
        except Exception:
            pass

    def run_test_normal(self, test):
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
                    raise TestCaseSkippedError('Testcase skipped by failure.')
        else:
            raise TestCaseSkippedError('Testcase disabled by filter.')

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
            start_time = time.time()

            if self.sequencer.dry_run:
                execution_time = test.dry_run()
            else:
                execution_time = None

                try:
                    self.run_test_normal(test)
                except TestCaseSkippedError as e:
                    LOGGER.info("testcase skipped: %s", e)
                    result = TestCase.SKIPPED
                    message = str(e)
                    raise
                except TestCaseXPassedError as e:
                    LOGGER.info("testcase xpassed: %s", e)
                    result = TestCase.XPASSED
                    message = str(e)
                    raise
                except TestCaseXFailedError as e:
                    LOGGER.info("testcase xfailed: %s", e)
                    result = TestCase.XFAILED
                    message = str(e)
                    raise
                except BaseException as e:
                    self.sequencer.run_failed = True
                    _log_traceback()
                    message = str(e)
                    raise

            result = TestCase.PASSED
        finally:
            finish_time = time.time()

            if execution_time is None:
                execution_time = (finish_time - start_time)

            log_lines(_TEST_FOOTER_FMT.format(name=test.name,
                                              result=result,
                                              duration=format_timespan(execution_time)))

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
                raise TestCaseFailedError(
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


def _log_traceback():
    for entry in traceback.format_exception(*sys.exc_info()):
        for line in entry.splitlines():
            LOGGER.error(line.rstrip())


def setup(name,
          parser=None,
          console_log_level=None,
          file_log_level=None):
    """Basic setup of a test program. Parses command line arguments,
    configures logging and creates a sequencer called `name`. Returns
    the sequencer.

    Give `parser` to use a custom argument parser. This functions
    appends its arguments to it.

    Use `console_log_level` to set the console log level.

    Use `file_log_level` to set the file log level.

    """

    if parser is None:
        parser = argparse.ArgumentParser()

    parser.add_argument('-c', '--no-continue-on-failure',
                        action='store_true',
                        help='Do not continue on test failure.')
    parser.add_argument(
        'test_pattern',
        metavar='test-pattern',
        nargs='?',
        help="Only run tests matching given regular expression pattern.")

    args = parser.parse_args()

    if not os.path.exists('logs'):
        os.mkdir('logs')

    configure_logging("logs/{name.replace(' ', '-')}",
                      console_log_level=console_log_level,
                      file_log_level=file_log_level)

    return Sequencer(name, testcase_pattern=args.test_pattern)
