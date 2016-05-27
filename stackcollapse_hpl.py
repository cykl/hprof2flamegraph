#! /usr/bin/env python
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

from __future__ import print_function

import struct
import collections
import sys
import re

Method = collections.namedtuple('Method', ['id', 'file_name', 'class_name', 'method_name'])
Trace = collections.namedtuple('Trace', ['thread_id', 'frame_count', 'frames'])
Frame = collections.namedtuple('Frame', ['bci', 'line_no', 'method_id'])

AGENT_ERRORS = [
    "No Java Frames[ERR=0]",
    "No class load[ERR=-1]",
    "GC Active[ERR=-2]",
    "Unknown not Java[ERR=-3]",
    "Not walkable not Java[ERR=-4]",
    "Unknown Java[ERR=-5]",
    "Not walkable Java[ERR=-6]",
    "Unknown state[ERR=-7]",
    "Thread exit[ERR=-8]",
    "Deopt[ERR=-9]",
    "Safepoint[ERR=-10]",
]


def parse_hpl_string(fh):
    (length,) = struct.unpack('>i', fh.read(4))
    (val,) = struct.unpack('>%ss' % length, fh.read(length))
    return val.decode('utf-8')


def parse_hpl(filename):
    traces = []
    methods = {}

    for (index, error) in enumerate(AGENT_ERRORS):
        method_id = -1 - index
        methods[method_id] = Method(method_id, "", "/Error/", error)

    with open(filename, 'rb') as fh:
        while True:
            marker_str = fh.read(1)
            if not marker_str:
                break

            (marker,) = struct.unpack('>b', marker_str)
            if marker == 0:
                break
            elif marker == 1:
                (frame_count, thread_id) = struct.unpack('>iQ', fh.read(4 + 8))
                if frame_count > 0:
                    traces.append(Trace(thread_id, frame_count, []))
                else:  # Negative frame_count are used to report error
                    if abs(frame_count) > len(AGENT_ERRORS):
                        method_id = frame_count - 1
                        methods[method_id] = Method(method_id, "Unknown err[ERR=%s]" % frame_count)
                    frame = Frame(None, None, frame_count - 1)
                    traces.append(Trace(thread_id, 1, [frame]))
            elif marker == 2:
                (bci, method_id) = struct.unpack('>iQ', fh.read(4 + 8))
                frame = Frame(bci, None, method_id)
                traces[-1].frames.append(frame)
            elif marker == 21:
                (bci, line_no, method_id) = struct.unpack('>iiQ', fh.read(4 + 4 + 8))
                if line_no < 0:  # Negative line_no are used to report that line_no is not available (-100 & -101)
                    line_no = None
                frame = Frame(bci, line_no, method_id)
                traces[-1].frames.append(frame)
            elif marker == 3:
                (method_id,) = struct.unpack('>Q', fh.read(8))
                file_name = parse_hpl_string(fh)
                class_name = parse_hpl_string(fh)
                method_name = parse_hpl_string(fh)
                methods[method_id] = Method(method_id, file_name, class_name, method_name)
            else:
                raise Exception("Unexpected marker: %s at offset %s" % (marker, fh.tell()))

    return traces, methods


def abbreviate_package(class_name):
    match_object = re.match(r'(?P<package>.*\.)(?P<remainder>[^.]+\.[^.]+)$', class_name)
    if match_object is None:
        return class_name

    shortened_pkg = re.sub(r'(\w)\w*', r'\1', match_object.group('package'))
    return "%s%s" % (shortened_pkg, match_object.group('remainder'))


def get_method_name(method, shorten_pkgs):
    class_name = method.class_name[1:-1].replace('/', '.')
    if shorten_pkgs:
        class_name = abbreviate_package(class_name)

    method_name = class_name
    method_name += '.' + method.method_name
    return method_name


def format_frame(frame, method, discard_lineno, shorten_pkgs):
    formatted_frame = get_method_name(method, shorten_pkgs)
    if not discard_lineno and frame.line_no:
        formatted_frame += ':' + str(frame.line_no)
    return formatted_frame


def main(argv=None, out=sys.stdout):
    import argparse

    parser = argparse.ArgumentParser(description='Convert an hpl file into Flamegraph collapsed stacks')
    parser.add_argument('hpl_file', metavar='FILE', type=str, nargs=1, help='A hpl file')
    parser.add_argument('--discard-lineno', dest='discard_lineno', action='store_true', help='Remove line numbers')
    parser.add_argument('--discard-thread', dest='discard_thread', action='store_true', help='Remove thread info')
    parser.add_argument('--shorten-pkgs', dest='shorten_pkgs', action='store_true', help='Shorten package names')
    parser.add_argument('--skip-trace-on-missing-frame', dest='skip_trace_on_missing_frame', action='store_true', help='Continue processing even if frames are missing')

    args = parser.parse_args(argv)
    filename = args.hpl_file[0]

    (traces, methods) = parse_hpl(filename)

    folded_stacks = collections.defaultdict(int)

    for trace in traces:
        frames = []
        skip_trace = False
        for frame in trace.frames:
            if args.skip_trace_on_missing_frame and not frame.method_id in methods:
                sys.stderr.write("skipped missing frame %s\n" % frame.method_id)
                skip_trace = True
                break
            frames.append(format_frame(
                frame,
                methods[frame.method_id],
                args.discard_lineno,
                args.shorten_pkgs
            ))

        if skip_trace:
            continue

        if not args.discard_thread:
            frames.append('Thread %s' % trace.thread_id)

        folded_stack = ';'.join(reversed(frames))
        folded_stacks[folded_stack] += 1

    for folded_stack in sorted(folded_stacks):
        sample_count = folded_stacks[folded_stack]
        print("%s %s" % (folded_stack, sample_count), file=out)

    return 0


if __name__ == '__main__':
    main()

