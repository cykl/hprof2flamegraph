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

import os
import unittest

try:
    # Python 2
    from StringIO import StringIO
except ImportError:
    # Python 3
    from io import StringIO

from stackcollapse_hprof import *

REF_DIR = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'ref', 'hprof')


def get_ref_file(with_lineno, with_thread):
    lineno = 'y' if with_lineno else 'n'
    thread = 'y' if with_thread else 'n'
    return os.path.join(
        REF_DIR,
        'cpu=samples,depth=100,interval=10,lineno={0},thread={1}.hprof.txt'.format(lineno, thread)
    )


refs = {
    get_ref_file(False, False): {
        'traceCount': 1692,
    },
    get_ref_file(False, True): {
        'traceCount': 884,
    },
    get_ref_file(True, False): {
        'traceCount': 884,
    },
    get_ref_file(True, True): {
        'traceCount': 890,
    },
}


class TestHeader(unittest.TestCase):

    def test_header_match_ok(self):
        header = "JAVA PROFILE 1.0.1, created Fri Jun 14 01:18:27 2013"
        self.assertTrue(header_match(header))

        header = "JAVA PROFILE 1.0.1, created Wed Jul  3 20:50:41 2013"
        self.assertTrue(header_match(header))

    def test_header_match_ko(self):
        header = "#! /user/bin/python"
        self.assertFalse(header_match(header))


class TestParsing(unittest.TestCase):

    def test_get_stack(self):
        for ref in refs:
            content = get_file_content(ref)
            stacks = get_stacks(content)
            self.assertEquals(refs[ref]['traceCount'], len(stacks))

    def test_get_counts(self):
        for ref in refs:
            content = get_file_content(ref)
            counts = get_counts(content)
            self.assertEquals(refs[ref]['traceCount'], len(counts))

    def test_same_key(self):
        for ref in refs:
            content = get_file_content(ref)
            stacks = get_stacks(content)
            counts = get_counts(content)

            ids = set()
            for id in stacks:
                ids.add(id)
            for id in counts:
                ids.add(id)

            self.assertEquals(len(stacks), len(ids))

    def test_is_tracing(self):
        filename = os.path.join(REF_DIR, 'cpu=times,depth=100,lineno=n,thread=n.hprof.txt')
        content = get_file_content(filename)
        self.assertTrue(is_tracing(content))

    def test_is_not_tracing(self):
        filename = get_ref_file(False, False)
        content = get_file_content(filename)
        self.assertFalse(is_tracing(content))

    def test_cpu_times(self):
        filename = os.path.join(REF_DIR, 'cpu=times,depth=100,lineno=n,thread=n.hprof.txt')
        content = get_file_content(filename)
        counts = get_counts(content)
        self.assertEquals(0, len(counts))


class TestStack(unittest.TestCase):

    def test_remove_unknown_lineno(self):
        line = 'java.lang.reflect.Constructor.newInstance(Constructor.java:Unknown line)'
        self.assertEquals(
            'java.lang.reflect.Constructor.newInstance',
            remove_unknown_lineno(line))

    def test_keep_lineno(self):
        line = 'java.net.URLClassLoader$1.run(URLClassLoader.java:355)'
        self.assertEquals(
            'java.net.URLClassLoader$1.run:355',
            remove_unknown_lineno(line, discard_lineno=False))

    def test_discard_lineno(self):
        line = 'java.net.URLClassLoader$1.run(URLClassLoader.java:355)'
        self.assertEquals(
            'java.net.URLClassLoader$1.run',
            remove_unknown_lineno(line, discard_lineno=True))

    def test_keep_thread(self):
        stack = "\n".join([
            'TRACE 301000: (thread=200001)',
            '\tjava.lang.ClassLoader.defineClass1(ClassLoader.java:Unknown line)',
            '\tjava.lang.ClassLoader.defineClass(ClassLoader.java:791)',
            ''
        ])
        stacks = get_stacks(stack, discard_thread=False)
        self.assertEquals(1, len(stacks))
        self.assertEquals(3, len(stacks['301000']))
        self.assertEquals("Thread 200001", stacks['301000'][2])

    def test_keep_thread_without_thread_info(self):
        stack = "\n".join([
            'TRACE 301000:',
            '\tjava.lang.ClassLoader.defineClass1(ClassLoader.java:Unknown line)',
            '\tjava.lang.ClassLoader.defineClass(ClassLoader.java:791)',
            ''
        ])
        stacks = get_stacks(stack, discard_thread=False)
        self.assertEquals(1, len(stacks))
        self.assertEquals(2, len(stacks['301000']))

    def test_discard_thread(self):
        stack = '\n'.join([
            'TRACE 301000: (thread=200001)',
            '\tjava.lang.ClassLoader.defineClass1(ClassLoader.java:Unknown line)',
            '\tjava.lang.ClassLoader.defineClass(ClassLoader.java:791)',
            ''
        ])
        stacks = get_stacks(stack, discard_thread=True)
        self.assertEquals(1, len(stacks))
        self.assertEquals(2, len(stacks['301000']))

    def test_abbreviate_package(self):
        self.assertEqual('f.b.Class.method', abbreviate_package("foo.bar.Class.method"))

    def test_shorten_pkgs(self):
        stack = "\n".join([
            'TRACE 301000: (thread=200001)',
            '\tjava.lang.ClassLoader.defineClass1(ClassLoader.java:Unknown line)',
            '\tjava.lang.ClassLoader.defineClass(ClassLoader.java:791)',
            ''
        ])
        stacks = get_stacks(stack, discard_thread=False, shorten_pkgs=True)
        self.assertEquals("j.l.ClassLoader.defineClass1", stacks['301000'][0])
        self.assertEquals("j.l.ClassLoader.defineClass:791", stacks['301000'][1])
        self.assertEquals("Thread 200001", stacks['301000'][2])


class TestCount(unittest.TestCase):

    def test_count(self):
        count = '\n'.join([
            'CPU SAMPLES BEGIN (total = 980) Fri Jun 14 01:11:49 2013',
            'rank   self  accum   count trace method',
            '   1  1.73%  1.73%      17 300993 java.lang.ClassLoader.defineClass1',
            '   2  1.12%  2.86%      11 301004 java.lang.Class.getDeclaredConstructors0',
            'CPU SAMPLES END',
        ])
        counts = get_counts(count)
        self.assertEquals(2, len(counts))
        self.assertEquals('17', counts['300993'])
        self.assertEquals('11', counts['301004'])


class TestEndToEnd(unittest.TestCase):

    def test_end_to_end(self):
        capturer = StringIO()
        main(argv=[get_ref_file(True, True)], out=capturer)
        content = capturer.getvalue()

        lines = [line for line in content.split('\n') if line]
        self.assertEquals(890, len(lines))
        ref = ';'.join([
            'java.security.SecureClassLoader.defineClass:142',
            'java.lang.ClassLoader.defineClass:791',
            'java.lang.ClassLoader.defineClass1 8',
        ])
        self.assertTrue(any(line.endswith(ref) for line in lines))
