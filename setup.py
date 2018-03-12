#!/usr/bin/env python

from setuptools import setup
import systest


if __name__ == "__main__":
    setup(name='systest',
          version=systest.__version__,
          description=('System test framework with serial and parallel execution.'),
          long_description=open('README.rst', 'r').read(),
          author='Erik Moqvist',
          author_email='erik.moqvist@gmail.com',
          license='MIT',
          classifiers=[
              'License :: OSI Approved :: MIT License',
              'Programming Language :: Python :: 2',
              'Programming Language :: Python :: 3',
          ],
          keywords=[
              'test',
              'system',
              'sequencer',
              'parallel'
          ],
          url='https://github.com/eerimoq/systest',
          py_modules=['systest'],
          test_suite="tests")
