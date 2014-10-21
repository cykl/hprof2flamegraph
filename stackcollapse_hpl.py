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
Frame = collections.namedtuple('Frame', ['line_no', 'method_id'])


def parse_hpl_string(fh):
    (length,) = struct.unpack('>i', fh.read(4))
    (val,) = struct.unpack('>%ss' % length, fh.read(length))
    return val.decode('utf-8')


def parse_hpl(filename):
    traces = []
    methods = {}

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
                traces.append(Trace(thread_id, frame_count, []))
            elif marker == 2:
                (line_no, method_id) = struct.unpack('>iQ', fh.read(4 + 8))
                frame = Frame(line_no, method_id)
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


def format_frame(frame, method, discard_lineno, shorten_pkgs):
    class_name = method.class_name[1:-1].replace('/', '.')
    if shorten_pkgs:
        class_name = abbreviate_package(class_name)

    formatted_frame = class_name
    formatted_frame += '.' + method.method_name
    if not discard_lineno:
        formatted_frame += ':' + str(frame.line_no)
    return formatted_frame


def main(argv=None, out=sys.stdout):
    import argparse

    parser = argparse.ArgumentParser(description='Convert an hpl file into Flamegraph collapsed stacks')
    parser.add_argument('hpl_file', metavar='FILE', type=str, nargs=1, help='A hpl file')
    parser.add_argument('--discard-lineno', dest='discard_lineno', action='store_true', help='Remove line numbers')
    parser.add_argument('--discard-thread', dest='discard_thread', action='store_true', help='Remove thread info')
    parser.add_argument('--shorten-pkgs', dest='shorten_pkgs', action='store_true', help='Shorten package names')

    args = parser.parse_args(argv)
    filename = args.hpl_file[0]

    (traces, methods) = parse_hpl(filename)

    folded_stacks = collections.defaultdict(int)

    for trace in traces:
        frames = [
            format_frame(
                frame,
                methods[frame.method_id],
                args.discard_lineno,
                args.shorten_pkgs
            ) for frame in trace.frames]

        if not args.discard_thread:
            frames.append('Thread %s' % trace.thread_id)

        folded_stack = ';'.join(reversed(frames))
        folded_stacks[folded_stack] += 1

    for folded_stack in folded_stacks:
        sample_count = folded_stacks[folded_stack]
        print("%s %s" % (folded_stack, sample_count), file=out)

    return 0


if __name__ == '__main__':
    main()