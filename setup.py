#!/usr/bin/env python

from setuptools import setup

setup(name='systest',
      version='0.4.0',
      description=('System test framework.'),
      long_description=open('README.rst', 'r').read(),
      author='Erik Moqvist',
      author_email='erik.moqvist@gmail.com',
      license='MIT',
      classifiers=[
          'License :: OSI Approved :: MIT License',
          'Programming Language :: Python :: 2',
          'Programming Language :: Python :: 3',
      ],
      keywords=['test',
                'system',
                'sequencer',
                'parallel'],
      url='https://github.com/eerimoq/systest',
      py_modules=['systest'],
      test_suite="tests")
