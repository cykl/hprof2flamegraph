# -*- coding: utf-8 -*-
#
# Copyright (c) 2014, Clément MATHIEU
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
# ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

from __future__ import division

import os
import unittest

try:
    # Python 2
    from StringIO import StringIO
except ImportError:
    # Python 3
    from io import StringIO

from stackcollapse_hpl import *


def get_ref_file(file_name):
    return os.path.join(os.path.dirname(os.path.realpath(__file__)), 'ref', 'hpl', file_name)


class AcceptanceTest(unittest.TestCase):

    def run_example_with(self, hpl_file="example.hpl", args=None):
        if not args:
            args = []

        capturer = StringIO()
        main(argv=[get_ref_file(hpl_file)] + args, out=capturer)
        content = capturer.getvalue()

        self.lines = [line for line in content.split('\n') if line]

    def test_should_have_5_lines(self):
        self.run_example_with()

        self.assertEqual(5, len(self.lines))

    def test_all_lines_should_end_with_space_number(self):
        self.run_example_with()

        for line in self.lines:
            self.assertTrue(re.match('.* \d+$', line), line)

    def test_should_contains_5_samples(self):
        self.run_example_with()

        sample_count = sum([int(line.split(" ")[-1]) for line in self.lines])
        self.assertEqual(5, sample_count)

    def test_should_contains_threads(self):
        self.run_example_with()

        for line in self.lines:
            self.assertTrue(re.match('^Thread \d+.*', line), line)

    def test_should_not_contains_threads(self):
        self.run_example_with(args=['--discard-thread'])

        for line in self.lines:
            self.assertFalse(re.match('^Thread \d+.*', line), line)
            self.assertTrue(re.match('^(java|com|Example|sun)', line), line)

    def test_standard_frame_does_not_contain_lineno(self):
        self.run_example_with()

        for line in self.lines:
            (collapsed_stack, _) = line.rsplit(' ', 1)
            for frame in collapsed_stack.split(';')[1:]:
                self.assertFalse(re.match('.*:-?\d+$', frame), frame)

    def test_most_frames_are_full_frame_which_contains_lineno(self):
        self.run_example_with(hpl_file="example_with_full_frame.hpl")

        with_lineno = 0
        without_lineno = 0

        for line in self.lines:
            (collapsed_stack, _) = line.rsplit(' ', 1)
            for frame in collapsed_stack.split(';')[1:]:
                if re.match('.*:\d+$', frame):
                    with_lineno += 1
                else:
                    without_lineno += 1

        self.assertTrue((with_lineno / (with_lineno + without_lineno)) > 0.85)

    def test_lineno_are_positives(self):
        self.run_example_with(hpl_file="example_with_full_frame.hpl")

        for line in self.lines:
            (collapsed_stack, _) = line.rsplit(' ', 1)
            for frame in collapsed_stack.split(';')[1:]:
                self.assertFalse(re.match('.*:-\d+$', frame), frame)

    def test_should_not_contains_lineno(self):
        self.run_example_with(hpl_file="example_with_full_frame.hpl", args=['--discard-lineno'])

        for line in self.lines:
            (collapsed_stack, _) = line.rsplit(' ', 1)
            for frame in collapsed_stack.split(';'):
                self.assertFalse(re.match('.*:-?\d+$', frame), frame)

    def test_should_fail_on_missing_method(self):
        if "assertRaisesRegexp" in dir(self):
            self.assertRaisesRegexp(
                KeyError, "1671214212",
                self.run_example_with, hpl_file="example-first-method-removed.hpl"
            )
        else:  # Python 2.6
            self.assertRaises(KeyError, self.run_example_with, hpl_file="example-first-method-removed.hpl")

    def test_should_continue_on_missing_method_when_asked(self):
        self.run_example_with()
        complete_lines = self.lines

        self.run_example_with(hpl_file="example-first-method-removed.hpl", args=['--skip-trace-on-missing-frame'])
        self.assertEqual(complete_lines[:-1], self.lines)

