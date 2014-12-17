#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (c) 2013, Clément MATHIEU
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

"""
Convert Java HPROF file into a flame graph.


Flame Graphs are great tools to visualize hot-CPU code-paths.
Brendan Gregg created them to be able to quickly troubleshoot performance issues.
He had huge amounts of stack sample and needed a way to visualize them. Its package
contains two scripts. The first one converts the DTrace output into an intermediary
representation. The second one creates the SVG graph from this representation.


This script aims to bring the same power to Java users. It allows to convert HPROF files
into the Flame Graph intermediary representation. flamegraph.pl from Brendan's project
still have to be run to create the final graph.

Usage example:
::
    java -agentlib:hprof=file=output.hprof,cpu=samples,depth=100,interval=10,lineno=y,thread=y [...]
    stackcollapse-hprof output.hprof | flamegraph.pl > graph.svg

"""

from __future__ import print_function

import re
import sys


def get_file_content(filename):
    """ Return the content of filename as a single string"""
    with open(filename, 'r') as f:
        lines = f.readlines()
        return "".join(lines)


def header_match(line):
    """ Return True if line match the HPROF header line, False otherwise"""
    pattern = 'JAVA PROFILE \d.\d.\d, created \w+ \w+ +\d+ \d{2}:\d{2}:\d{2} \d{4}'
    return re.match(pattern, line) is not None


def remove_unknown_lineno(stack_element, discard_lineno=False):
    """ Process a stack_element to adjust lineno.

    If lineno is unknown remove it. If lineno is set remove the superfluous file
    information.
    """
    pattern = r'(?P<start>.+)\((.+):(?P<line>.+)\)'
    match_object = re.match(pattern, stack_element)
    if match_object.group('line') == 'Unknown line':
        return match_object.group('start')

    if discard_lineno:
        return match_object.group('start')
    else:
        return '{0}:{1}'.format(
            match_object.group('start'),
            match_object.group('line'))


def abbreviate_package(stack_line):
    """ Abbreviate the package from a stack line: foo.bar.Class.method -> f.b.Class.method

    In a package name cannot be found the string is unchanged
    """
    match_object = re.match(r'(?P<package>.*\.)(?P<remainder>[^.]+\.[^.]+)$', stack_line)
    if match_object is None:
        return stack_line

    shortened_pkg = re.sub(r'(\w)\w*', r'\1', match_object.group('package'))
    return "%s%s" % (shortened_pkg, match_object.group('remainder'))


def _process_stack(stack, discard_lineno=False, shorten_pkgs=False):
    """ Process an HPROF stack to only get meaningful content"""
    stack = stack.split('\n')
    stack = [line.strip() for line in stack if line]
    stack = [remove_unknown_lineno(line, discard_lineno) for line in stack]
    if shorten_pkgs:
        stack = [abbreviate_package(line) for line in stack]
    return stack


def get_stacks(content, discard_lineno=False, discard_thread=False, shorten_pkgs=False):
    """ Get the stack traces from an hprof file. Return a dict indexed by trace ID. """
    stacks = {}

    pattern = r'TRACE (?P<trace_id>[0-9]+):( \(thread=(?P<thread_id>[0-9]+)\))?\n(?P<stack>(\t.+\n)+)'
    match_objects = re.finditer(pattern, content, re.M)
    for match_object in match_objects:
        trace_id  = match_object.group('trace_id')
        if "<empty>" in match_object.group('stack'):
            continue
        stack     = _process_stack(match_object.group('stack'), discard_lineno, shorten_pkgs)
        thread_id = match_object.group('thread_id')
        if thread_id and not discard_thread:
            stack.append("Thread {0}".format(thread_id))

        stacks[trace_id] = stack

    return stacks


def get_counts(content):
    """ Get the sample counts from an hprof file. Return a dict indexed by trace ID"""
    def extract_trace_and_count(sample):
        """ Extract the trace and count fields from a sample line"""
        fields = sample.split()
        count = fields[3]
        trace = fields[4]
        return trace, count

    pattern = r'CPU SAMPLES BEGIN \(total = \d+\).+\nrank[^\n]+\n(?P<samples>([^\n]+\n)+)CPU SAMPLES END'
    match_object = re.search(pattern, content, re.M)
    if not match_object:
        return {}

    samples = filter(None, match_object.group('samples').split('\n'))

    counts = {}
    for trace, count in [extract_trace_and_count(t) for t in samples]:
        counts[trace] = count

    return counts


def is_tracing(content):
    """ Return True is the the cpu mode was tracing and not sampling"""
    pattern = r'CPU TIME \(ms\) BEGIN'
    return re.search(pattern, content, re.M) is not None


def to_flamegraph(stacks, counts):
    """ Convert the stack dumps and sample counts into the flamegraph format.

    Return a list of lines.
    """
    lines = []
    for id in counts:
        stack = ";".join(reversed(stacks[id]))
        count = counts[id]
        lines.append('{0} {1}'.format(stack, count))

    return lines


def main(argv=None, out=sys.stdout):
    import argparse
    parser = argparse.ArgumentParser(description='Convert an HPROF file into the flamegraph format')
    parser.add_argument('hprof_file', metavar='FILE', type=str, nargs=1, help='An HPROF file')
    parser.add_argument('--discard-lineno', dest='discard_lineno', action='store_true', help='Remove line numbers')
    parser.add_argument('--discard-thread', dest='discard_thread', action='store_true', help='Remove thread information')
    parser.add_argument('--shorten-pkgs', dest='shorten_pkgs', action='store_true', help='Shorten package names')

    args = parser.parse_args(argv)
    filename = args.hprof_file[0]
    content  = get_file_content(filename)

    if not header_match(content):
        sys.exit('{0} is not an hprof file'.format(filename))

    if is_tracing(content):
        sys.exit('CPU tracing is not supported. Please use sampling.')

    stacks = get_stacks(content, args.discard_lineno, args.discard_thread, args.shorten_pkgs)
    if not stacks:
        sys.exit('Failed to get TRACE')

    counts = get_counts(content)
    if not counts:
        sys.exit('Failed to get samples.')

    for line in to_flamegraph(stacks, counts):
        print(line, file=out)

    return 0


if __name__ == '__main__':
    main()
