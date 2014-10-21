.. image:: https://travis-ci.org/cykl/hprof2flamegraph.svg?branch=release
    :target: https://travis-ci.org/cykl/hprof2flamegraph


*****************
Java flame graphs
*****************

A few years ago, Brendan Gregg created the `flame graph visualization`_. He describes it as
*a visualization of profiled software, allowing the most frequent code-paths to be identified
quickly and accurately*. More pragmatically, it is a great way to identify the hot spots of
an application and to understand its runtime behavior.

The FlameGraph_ project provides a `flamegraph.pl` script to create SVG files
from a pivot format called *folded stacks*, and several scripts to convert the
proprietary output of various profilers (perf, DTrace etc.) into folded stacks.

This project aims to provide conversion scripts for several Java profilers.
These scripts are not pushed in the official project mostly because they are written
in Python and not in Perl.

Supported profilers are:

- HPROF_
- `Honest-profiler`_


.. _flame graph visualization: http://www.brendangregg.com/flamegraphs.html
.. _FlameGraph: https://github.com/brendangregg/FlameGraph
.. _HPROF: http://docs.oracle.com/javase/7/docs/technotes/samples/hprof.html
.. _Honest-profiler: https://github.com/RichardWarburton/honest-profiler


Installation
============

The easiest way to install `hprof2flamgegraph` is to use the
`Pypi package`_:

.. code-block:: bash

        pip install [--user] hprof2flamegraph

It installs a `stackcollapse-hprof` and `stackcollapse-hpl` scripts into
the `bin` directory of your environment. Make sure this directory is in
your `PATH`. The original `flamegraph.pl` script from Brendan is also
installed (CDDL licensed).

You can also download the script from github or clone the repository.
The script is standalone with Python >= 2.7 and only requires the `argparse`
module with Python 2.6.

.. _Pypi package: http://pypi.python.org/pypi/hprof2flamegraph


Why should I use flame graphs with a Java profiler ?
====================================================

The Java ecosystem is full of great performance analysis tools and profilers.
They are often full featured (CPU, memory, threads, GC, monitors, etc.) and well
suited for complex environments or analyses.

However, quite often we only need to get the big picture of our application.
Flame graphs really shine in this area. It is the easiest and fastest way to visualize
your application and understand its performance profile. It is a complement to
more heavy-weight analysis environments.

The official `flame graph visualization`_ page describe it in-depth and examine several
use cases.


Usage
=====

HPROF
-----

Run the application with HPROF enabled. It must be configured to
do CPU sampling and not CPU tracing. You can configure the sampling
interval, the maximum stack depth, and whether if line numbers and
thread information are printed.

I recommend to always set these last two to `y` since they can be
discarded at a latter step if needed. You never collect too much information.


.. code-block:: bash

  java -agentlib:hprof=cpu=samples,depth=100,interval=7,lineno=y,thread=y,file=output.hprof[...]

Convert the `output.hprof` file into folded stacks using the *stackcollapse-hprof* script

.. code-block:: bash

  stackcollapse-hprof output.hprof > output-folded.txt

Create the final SVG graph. You can either use the `flamegraph.pl` script shipped with this
module or the one from the official FlameGraph project. They are the same.

.. code-block:: bash

  flamegraph.pl output-folded.txt > output.svg

A few tips about HPROF follows:

- HPROF is not hot-pluggable. It means that it must be activated when the JVM starts and that
  the application will be profiled from the begging to the end. However, playing with SIGQUITs
  allow to profile a specific time frame. Its lame but it works.

- It is also usually a good practice to avoid round sampling intervals like 10ms to avoid a
  possible bias due to the synchronization of several periodic processes (like a process
  scheduler or a timer).

- As shown in `Evaluating the Accuracy of Java Profilers`_ HPROF is flawed, like many other Java
  profiler, and can produce non-actionable profiles. It worth reading the paper to make sure you
  understand the limitation of the tool. After that, HPROF is usually good enough to identify the
  hot spots.

.. _Evaluating the Accuracy of Java Profilers: http://pl.cs.colorado.edu/papers/mytkowicz-pldi10.pdf

Honest-profiler
---------------

Run the application with `honest-profiler enabled`_  (and remember it is **not production ready yet**).

.. code-block:: bash

   java -agentpath:/path/to/location/liblagent.so[...]

It will create a *log.hpl*. Convert it into folded stacks using the *stackcollapse-hpl* script

.. code-block:: bash

  stackcollapse-hpl log.hpl > output-folded.txt

Create the final SVG graph

.. code-block:: bash

  flamegraph.pl output-folded.txt > output.svg

.. _honest-profiler enabled: https://github.com/RichardWarburton/honest-profiler/wiki/How%20to%20Run


Specific use cases
==================

Hadoop jobs
-----------

Want to profile an Hadoop job?

It is quite easy to do. You only have to set the following Hadoop variables:

- `mapred.task.profile`
- `mapred.task.profile.params`
- `mapred.task.profile.maps`
- `mapred.task.profile.reduces`.

To enable HPROF programmatically from a Java job:

.. code-block:: java

  Configuration conf = getConf();
  conf.setBoolean("mapred.task.profile", true);
  conf.set("mapred.task.profile.params",
           "-agentlib:hprof=cpu=samples,depth=100,interval=7,lineno=y,thread=y,file=%s");
  conf.set("mapred.task.profile.maps", "0");
  conf.set("mapred.task.profile.reduces", "0");

To do it from the command line:

.. code-block:: bash

  hadoop jar my.jar \
    -Dmapred.task.profile=true \
    -Dmapred.task.profile.params="-agentlib:hprof=cpu=samples,depth=100,interval=7,lineno=y,thread=y,file=%s" \
    -Dmapred.task.profile.maps=0 \
    -Dmapred.task.profile.reduces=0

