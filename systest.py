from __future__ import print_function

from abc import ABCMeta, abstractmethod
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
from six import add_metaclass


__author__ = 'Erik Moqvist'
__version__ = '5.4.0'


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

_DIGRAPH_FMT = '''\
digraph {name} {{
    {begin_id} [label="begin" shape=box];
    {end_id} [label="end" shape=box];

{nodes}

{deps}
}}
'''

LOGGER = logging.getLogger(__name__)


def configure_logging(filename=None):
    """Configure the logging module to write output to the console and a
    file. The file name is `filename-<date>.log` if `filename` is not
    None, otherwise the file name is ``systest-<date>.log``.

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

    filename = "{}-{}.log".format(filename,
                                  _make_filename(str(datetime.datetime.now())))

    # Create any missing parent log file folders.
    dirname = os.path.dirname(filename)

    if dirname:
        if not os.path.exists(dirname):
            os.makedirs(dirname)

    file_handler = logging.FileHandler(filename, "w")
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s %(name)s %(levelname)s %(message)s"))
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


# Deprecated. To be removed.
SequencerTestFailedError = TestCaseFailedError
SequencerTestSkippedError = TestCaseSkippedError


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
                '{}:{}: {} is not equal to {}'.format(filename,
                                                      line,
                                                      repr(first),
                                                      repr(second)))

    def assert_not_equal(self, first, second):
        """Raise an exception if ``first`` and ``second`` are equal.

        """

        if first == second:
            filename, line, _, _ = traceback.extract_stack()[-2]

            raise TestCaseFailedError(
                '{}:{}: {} is equal to {}'.format(filename,
                                                  line,
                                                  repr(first),
                                                  repr(second)))

    def assert_true(self, condition):
        """Raise an exception if given condition `condition` is false.

        """

        if not condition:
            filename, line, _, _ = traceback.extract_stack()[-2]

            raise TestCaseFailedError('{}:{}: {} is not true'.format(filename,
                                                                     line,
                                                                     condition))

    def assert_false(self, condition):
        """Raise an exception if given condition `condition` is true.

        """

        if condition:
            filename, line, _, _ = traceback.extract_stack()[-2]

            raise TestCaseFailedError('{}:{}: {} is not false'.format(filename,
                                                                      line,
                                                                      condition))

    def assert_in(self, member, container):
        """Raise an exception if given member `member` is not found in given
        container `container`.

        """

        if member not in container:
            filename, line, _, _ = traceback.extract_stack()[-2]

            raise TestCaseFailedError(
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

            raise TestCaseFailedError(
                '{}:{}: {} found in {}'.format(filename,
                                               line,
                                               repr(member),
                                               repr(container)))

    def assert_is_none(self, obj):
        """Raise an exception if given object `obj` is not None.

        """

        if obj is not None:
            filename, line, _, _ = traceback.extract_stack()[-2]

            raise TestCaseFailedError(
                '{}:{}: {} is not None'.format(filename,
                                               line,
                                               repr(obj)))

    def assert_is_not_none(self, obj):
        """Raise an exception if given object `obj` is None.

        """

        if obj is None:
            filename, line, _, _ = traceback.extract_stack()[-2]

            raise TestCaseFailedError(
                '{}:{}: {} is None'.format(filename,
                                           line,
                                           repr(obj)))

    def assert_greater(self, first, second):
        """Raise an exception if ``first`` is not greater than ``second``.

        """

        if first <= second:
            filename, line, _, _ = traceback.extract_stack()[-2]

            raise TestCaseFailedError(
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

            raise TestCaseFailedError(
                '{}:{}: {} is not greater than or equal to {}'.format(filename,
                                                                      line,
                                                                      repr(first),
                                                                      repr(second)))

    def assert_less(self, first, second):
        """Raise an exception if ``first`` is not less than ``second``.

        """

        if first >= second:
            filename, line, _, _ = traceback.extract_stack()[-2]

            raise TestCaseFailedError(
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

            raise TestCaseFailedError(
                '{}:{}: {} is not less than or equal to {}'.format(filename,
                                                                   line,
                                                                   repr(first),
                                                                   repr(second)))

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
                        '{}:{}: {} not raised'.format(filename, line, name))
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

            raise TestCaseFailedError('{}:{}: {} is not None'.format(filename,
                                                                     line,
                                                                     repr(obj)))


@add_metaclass(ABCMeta)
class ResultVisitor(object):
    @abstractmethod
    def visit_test(self, test):
        """
        Called for each result in the result tree.

        :param test: TestCase object.
        :return:
        """
        raise NotImplementedError('Abstract method must be overridden')

    @abstractmethod
    def start_serial(self):
        raise NotImplementedError('Abstract method must be overridden')

    @abstractmethod
    def end_serial(self):
        raise NotImplementedError('Abstract method must be overridden')

    @abstractmethod
    def start_parallel(self):
        raise NotImplementedError('Abstract method must be overridden')

    @abstractmethod
    def end_parallel(self):
        raise NotImplementedError('Abstract method must be overridden')


class CountReport(ResultVisitor):
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.skipped = 0
        self.xpassed = 0
        self.xfailed = 0

    def visit_test(self, test):
        """
        Tallies state of each visited test.
        """
        if test.result == TestCase.PASSED:
            self.passed += 1
        elif test.result == TestCase.FAILED:
            self.failed += 1
        elif test.result == TestCase.XPASSED:
            self.xpassed += 1
        elif test.result == TestCase.XFAILED:
            self.xfailed += 1
        else:
            self.skipped += 1

    def start_serial(self):
        pass

    def end_serial(self):
        pass

    def start_parallel(self):
        pass

    def end_parallel(self):
        pass

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
        if self.failed > 0:
            result = TestCase.FAILED
        else:
            result = TestCase.PASSED

        return ('{} (passed: {}, failed: {}, skipped: {}, xpassed: {}, '
                'xfailed: {})').format(result,
                                       self.passed,
                                       self.failed,
                                       self.skipped,
                                       self.xpassed,
                                       self.xfailed)


class SummaryReporter(ResultVisitor):
    _SUMMARY_FMT = '''
    ---------------------- Test summary begin ----------------------

    {summary}

    Execution time: {execution_time}
    Result: {result}

    ----------------------- Test summary end -----------------------
    '''
    def __init__(self):
        self._indent = -4
        self._summary = []

    def visit_test(self, test):
        """
        Summarises each visited test.

        :param test:
        :return:
        """
        fmt = ' ' * self._indent + test.name + ': {result}{message}'

        if test.result:
            result = test.result
        else:
            result = TestCase.SKIPPED

        if test.message is None:
            message = ''
        else:
            message = ' ({})'.format(test.message)

        self._summary.append(fmt.format(result=result, message=message))

    def start_serial(self):
        self._summary.append(' ' * self._indent + '[')
        self._indent += 4

    def end_serial(self):
        self._indent -= 4
        self._summary.append(' ' * self._indent + ']')

    def start_parallel(self):
        self._summary.append(' ' * self._indent + '(')
        self._indent += 4

    def end_parallel(self):
        self._indent -= 4
        self._summary.append(' ' * self._indent + ')')

    def _test(self, test, indent):
        return [self.summary_test(test, indent)]

    def __str__(self):
        return '\n'.join(self._summary)


class JsonReporter(ResultVisitor):
    def __init__(self):
        self._structure = None
        self._path = []

    def visit_test(self, test):
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

        self._path[-1].append(summary)

    def start_serial(self):
        new_list = []
        self._path[-1].append(new_list)
        self._path.append(new_list)
        if self._structure is None:
            self._structure = new_list

    def end_serial(self):
        self._path.pop()

    def start_parallel(self):
        new_list = []
        self._path[-1].append(new_list)
        self._path.append(new_list)
        if self._structure is None:
            self._structure = new_list

    def end_parallel(self):
        self._path.pop()

    def report(self):
        return odict([
            ('name', self.name),
            ('date', str(datetime.datetime.now())),
            ('node', platform.node()),
            ('user', getpass.getuser()),
            ('testcases', self._structure)
        ])

    def write_report(self, output_file):
        if hasattr(output_file, 'write'):
            output_file.write(json.dumps(self.report(), indent=4))
        else:
            with open(output_file, 'w') as fout
                fout.write(json.dumps(self.summary_json(), indent=4))


class GraphReporter(ResultVisitor):
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

    def __init__(self):
        # Create the begin test case node.
        begin = TestCase("begin")
        begin.result = TestCase.PASSED
        begin.finish_time = 0.0

        # Use begin as the parent of the first test case.
        self._parent = [begin]

        # Create the end test case node.
        #end = TestCase("end")
        #end.result = TestCase.PASSED
        #end.execution_time = 0.0

        self._edges = {}
        self._nodes = []
        self._deps = []

    def visit_test(self, test):
        def edge_name(parent, test):
            return '{}  ->  {}'.format(id(parent), id(test))

        self._nodes.append('    {} [label="{}"]'.format(id(test), test.name))
        if test.result:
            self._deps.append(str(self._edges[edge_name(self._parent[-1], test)]))

        test.parents = parents

        if test.result:
            test.start_parent = get_start_parent(test)
            test.finish_time = test.start_parent.finish_time + test.execution_time

        self._parent[-1] = test

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

        # Bold edges in the slowest execution path.
        edges_recursivly(edges, end, "bold")


    def start_serial(self):
        pass

    def end_serial(self):
        pass

    def start_parallel(self):
        self._parent.append(None)

    def end_parallel(self):
        self._parent.pop()

    def dot_graph(self):
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


        return _DIGRAPH_FMT.format(name=_make_filename(self.name),
                                   begin_id=id(begin),
                                   end_id=id(end),
                                   nodes='\n'.join(self._nodes),
                                   deps='\n'.join(self._deps))

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
        self._reporters = []

    def register_reporter(self, reporter):
        self._reporters.append(reporter)

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
