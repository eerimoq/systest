|buildstatus|_

Installation
============

.. code-block:: python

    pip install systest

Description
===========

Execute a sequence of test cases in serial and/or parallel.

Test cases in a list are executed in serial and test cases in a tuple are
executed in parallel, in separate Python threads.

This framework is created with production test in mind, trying to make it
possible to minimize the test execution time by executing tests in parallel. The
framework is *not* indended as a replacement for ``unittest``, but rather to be
a complement to it.

Documentation: http://systest.readthedocs.org/en/latest

Example usage
=============

See the test suite: https://github.com/eerimoq/systest/blob/master/tests/test_systest.py

For example, the sequence below starts with test case ``MyTestCase("1")``. When
``MyTestCase("1")`` has been executed, ``MyTestCase("2")`` and the list of
``MyTestCase("3")`` and ``MyTestCase("4")`` are executed in parallel. When both
``MyTestCase("2")`` and the list of ``MyTestCase("3")`` and ``MyTestCase("4")``
has been executed, ``MyTestCase("5")`` is executed. Then the sequence ends.

.. code-block:: python

   import logging
   from systest import TestCase, Sequencer, configure_logging

   LOGGER = logging.getLogger(__name__)

   # Define a testcase.
   class MyTestCase(TestCase):

       def __init__(self, name):
           super(MyTestCase, self).__init__()
           self.name = "my_testcase_" + name

       def run(self):
           LOGGER.info("Hello!")

   # Configure the logging module.
   configure_logging()

   sequencer = Sequencer("my_sequence")

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

The output is:

.. code-block:: text

   Name: my_sequence
   Date: 2016-02-02 18:42:40.446213
   Node: erik-VirtualBox
   User: erik
   ---------------------------------------------------------------
   Name: my_testcase_1
   Description:
   None
   Hello!
   
   my_testcase_1: PASSED in 0m 0s
   ---------------------------------------------------------------
   Name: my_testcase_2
   Description:
   None
   Hello!
   
   my_testcase_2: PASSED in 0m 0s
   ---------------------------------------------------------------
   Name: my_testcase_3
   Description:
   None
   Hello!
   
   my_testcase_3: PASSED in 0m 0s
   ---------------------------------------------------------------
   Name: my_testcase_4
   Description:
   None
   Hello!
   
   my_testcase_4: PASSED in 0m 0s
   ---------------------------------------------------------------
   Name: my_testcase_5
   Description:
   None
   Hello!
   
   my_testcase_5: PASSED in 0m 0s
   
   ---------------------- Test summary begin ----------------------
   
   [
       [
           my_testcase_1: PASSED,
           (
               my_testcase_2: PASSED,
               [
                   my_testcase_3: PASSED,
                   my_testcase_4: PASSED
               ]
           ),
           my_testcase_5: PASSED
       ]
   ]
   
   Execution time: 0m 0s
   
   ----------------------- Test summary end -----------------------

.. |buildstatus| image:: https://travis-ci.org/eerimoq/systest.svg
.. _buildstatus: https://travis-ci.org/eerimoq/systest
