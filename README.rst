
****************
hprof2flamegraph
****************

A few years ago, Brendan Gregg created the `flame graph visualization`_. It allows
to visualize a collection of sampled stack traces to discover the hotspots of
an application.

The Java ecosystem is full of great performance analysis tools and profilers.
They are often full featured (CPU, memory, threads, GC, monitors, etc.) and well
suited for complex environments or analyses. However, quite often we only
need to get the big picture of our application. This is especially true in
single threaded CPU bound applications like batchs or map reduce jobs.
Flamegraph really shines in this area. It is my favorite tool to quickly
discover how I can enhance my jobs to make them several times faster by
rewriting only a few lines of code. 

`hprof2flamegraph` converts the output of HPROF_  into folded stacks which is the
input format of Brendan's FlameGraph_.

.. _flame graph visualization: http://dtrace.org/blogs/brendan/2011/12/16/flame-graphs/
.. _HPROF: http://docs.oracle.com/javase/7/docs/technotes/samples/hprof.html
.. _FlameGraph: https://github.com/brendangregg/FlameGraph

Usage
=====

Firstly, enable HPROF and run your application. CPU sampling 
must be enabled (not tracing). You can configure the 
sampling interval, the maximum stack depth, and whether if
line numbers and thread information are printed. I recommend
to always set them to `y` since they can be discarded at a 
latter step if needed. You never have too much information.


.. code-block:: bash

  java -agentlib:hprof=cpu=samples,depth=100,interval=1ms,lineno=y,thread=y,file=output.hprof[...]

Secondly, use `hprof2flamegraph` to convert the HPROF output 
into the folded stacks format.

.. code-block:: bash

  hprof2flamegraph output.hprof > output-folded.txt

Finally, use `flamegraph.pl` to create the final SVG graph.

.. code-block:: bash

  flamegraph.pl output-folded.txt > output.svg

Want to profile an Hadoop job? It is quite easy too. You must set the
following Hadoop variables: `mapred.task.profile`, `mapred.task.profile.params`,
`mapred.task.profile.maps`, `mapred.task.profile.reduces`. For example, to do
it programmatically from a Java job:

.. code-block:: java

  Configuration conf = getConf();
  conf.setBoolean("mapred.task.profile", true);
  conf.set("mapred.task.profile.params", 
           "-agentlib:hprof=cpu=samples,depth=100,interval=5ms,lineno=y,thread=y,file=%s");
  conf.set("mapred.task.profile.maps", "0");
  conf.set("mapred.task.profile.reduces", "0");


Installation
============

The easiest way to install `hprof2flamgegraph` is to use the 
`Pypi package`_:

.. code-block:: bash

        pip install [--user] hprof2flamegraph

It installs a `hprof2flamegraph` script into the `bin` directory of your
environment. Make sure this directory is in your `PATH`. The original
`flamegraph.pl` script from Brendan is also installed (CDDL licensed). 

You can also download the script from github or clone the repository. 
The script is standalone with Python >= 2.7 and only requires the `argparse`
module with Python 2.6. 


.. _Pypi package: http://pypi.python.org/pypi/hprof2flamegraph
