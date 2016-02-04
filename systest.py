from __future__ import print_function

import sys
import threading
import time
import datetime
import getpass
import platform
import string
import subprocess

__author__ = 'Erik Moqvist'

_RUN_HEADER_FMT ="""
Name: {name}
Date: {date}
Node: {node}
User: {user}"""

_TEST_HEADER_FMT = """---------------------------------------------------------------
Name: {name}
Description:
{description}"""

_TEST_FOOTER_FMT = """
{name}: {result} in {duration}"""

_SUMMARY_FMT = """
---------------------- Test summary begin ----------------------

{summary}

Execution time: {execution_time}

----------------------- Test summary end -----------------------
"""

_DIGRAPH_FMT = """digraph {name} {{
    begin [shape=box];
    end [shape=box];

{deps}
}}
"""

def _make_filename(text):
    result = ""

    for char in text:
        if char in string.digits + string.ascii_letters + "._":
            result += char
        else:
            result += "_"

    return result


def _color_passed(text):
    return '\033[0;32m' + text + '\033[0m'


def _color_failed(text):
    return '\033[0;31m' + text + '\033[0m'


def _color_skipped(text):
    return '\033[0;33m' + text + '\033[0m'


def _color_result(result):
    if result == TestCase.PASSED:
        return _color_passed(TestCase.PASSED)
    elif result == TestCase.FAILED:
        return _color_failed(TestCase.FAILED)
    elif result == TestCase.SKIPPED:
        return _color_skipped(TestCase.SKIPPED)
    else:
        raise ValueError("bad result: {}".format(result))


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
        except SequencerTestFailedError:
            pass

    def run_test(self, test):
        print(_TEST_HEADER_FMT.format(name=test.name,
                                      description=test.__doc__),
              file=self.sequencer.output_stream)

        test.sequencer = self.sequencer

        try:
            result = TestCase.FAILED

            # run the test
            if self.sequencer.dry_run:
                start_time = None
                execution_time = test.dry_run()
            else:
                start_time = time.time()
                test.run()

            result = TestCase.PASSED
        finally:
            finish_time = time.time()

            if start_time is not None:
                execution_time = (finish_time - start_time)

            print(_TEST_FOOTER_FMT.format(name=test.name,
                                          result=result,
                                          duration=_human_time(execution_time)),
                  file=self.sequencer.output_stream)

            test.result = result
            test.execution_time = execution_time
            test.finish_time = finish_time

    def run_sequential_tests(self, tests):
        """Run all tests in the list in sequential order.

        """

        for test in tests:
            thread = _TestThread(test, self.sequencer)
            thread.start()
            thread.join()

            # raise an exception if the test failed
            if self.sequencer.stop_on_failure and thread.result == TestCase.FAILED:
                raise SequencerTestFailedError("The testcase failed.")

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
                raise SequencerTestFailedError("At least one of the parallel testcases failed.")

    def run_tests(self, tests):
        """Run the test(s).

        """

        if isinstance(tests, TestCase):
            if self.sequencer.is_testcase_enabled(tests):
                self.run_test(tests)
        elif isinstance(tests, list):
            self.run_sequential_tests(tests)
        elif isinstance(tests, tuple):
            if self.sequencer.force_serial_execution:
                self.run_sequential_tests(tests)
            else:
                self.run_parallel_tests(tests)


class SequencerTestFailedError(Exception):
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
        self.sequencer = None
        self.execution_time = None
        self.finish_time = None
        self.parents = []
        self.start_parent = None

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

    def log(self, text):
        """Write given text to the sequencer log.

        """

        entry = self.sequencer.format_log_entry(self.name + " " + text)
        self.sequencer.log(entry)

    def assert_equal(self, first, second):
        """Raise an exception if ``first`` and ``second`` are not equal.

        """

        if first != second:
            raise RuntimeError("{} != {}".format(first, second))


class Sequencer(object):

    def __init__(self,
                 name,
                 output_stream=None,
                 color=True,
                 stop_on_failure=True,
                 testcase_filter=None,
                 dry_run=False,
                 force_serial_execution=False):
        self.name = name
        if output_stream is None:
            self.output_stream = sys.stdout
        else:
            self.output_stream = output_stream
        self.stop_on_failure = stop_on_failure
        self.dry_run = dry_run
        self.tests = None
        self.execution_time = 0.0
        self.color = color
        self.testcase_filter = testcase_filter
        self.force_serial_execution = force_serial_execution

    def is_testcase_enabled(self, test):
        if self.testcase_filter is None:
            return True

        return test.name in self.testcase_filter

    def log(self, text):
        """Write given text to the output stream. The default output stream is
        standard output.

        """

        print(text, file=self.output_stream)

    def format_log_entry(self, text=None):
        """Write a timestamp and given text to the output stream. The default
        output stream is standard output.

        """

        if text is None:
            return ""
        else:
            return str(datetime.datetime.now()) + " " + text

    def run(self, *tests):
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
            print(_RUN_HEADER_FMT.format(name=self.name,
                                         date=datetime.datetime.now(),
                                         node=platform.node(),
                                         user=getpass.getuser()),
                  file=self.output_stream)
            self.tests = []

        self.tests += list(tests)

        start_time = time.time()

        thread = _TestThread(list(tests), self)
        thread.start()
        thread.join()

        end_time = time.time()
        self.execution_time += (end_time - start_time)

        # raise an exception if at least one test failed
        if thread.result != TestCase.PASSED:
            raise SequencerTestFailedError("At least one testcase failed.")

    def summary(self):
        """Compile the test execution summary and return it as a string.

        """

        def test(test, indent):
            fmt = ' ' * indent + test.name + ': {result}'

            if test.result:
                result = test.result
            else:
                result = TestCase.SKIPPED
            if self.color:
                result = _color_result(result)

            return [fmt.format(result=result)]

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

        return _SUMMARY_FMT.format(summary=summary,
                                   execution_time=_human_time(self.execution_time))

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
                return ('    "{parent_name}" -> "{name}" [label="{parent_finish_time}"'
                        ', style="{style}"];').format(
                            parent_name=self.parent.name,
                            name=self.test.name,
                            parent_finish_time=_human_time(self.parent.finish_time),
                            style=self.style)

        def edge_name(parent, test):
            return parent.name + " -> " + test.name

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

        return _DIGRAPH_FMT.format(name=_make_filename(self.name),
                                   deps='\n'.join([str(dep) for dep in deps]))

    def report(self):
        """Print a summary and create a dot graph image.

        """

        print(self.summary())

        filename = _make_filename(self.name)
        filename_dot = filename + ".dot"
        filename_png = filename + ".png"

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
