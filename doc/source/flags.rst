=======================================
 Using Command-Line Flags in Infra.git
=======================================

Processing command-line arguments (aka flags) is done using the standard Python
argparse module, with a very thin convenience layer on top of it. 

One design principle is that flags are defined per-package. To be consistent
across the codebase, it is recommended that **each package defines the top-level
functions ``add_argparse_options`` and ``process_argparse_options``**. The first
is supposed to define flags by calling methods like
``ArgumentParser.add_argument()``, plus do some minor processing without any
side-effect. The second function does some package-level processing based on the
result of the parsed command-line.

Example usage from a top-level script, with the ``infra_libs.logs`` package:

.. code-block:: python

  import argparse
  import infra_libs.logs
  
  parser = argparse.ArgumentParser()
  infra_libs.logs.add_argparse_options(parser)
  
  options = parser.parse_args()
  infra_libs.logs.process_argparse_options(options)

As more packages add their own flags, the output of ``--help`` can quickly
become unreadable. To help with that, it is recommended that

- each package defines an option group
- each option for a given package starts with the same prefix

Example (from the ``infra_libs.ts_mon`` package):

.. code-block:: python

  def add_argparse_options(parser):
    parser = parser.add_argument_group('Timeseries Monitoring Options')
    parser.add_argument(
      '--ts-mon-endpoint',
      default='https://www.googleapis.com/acquisitions/v1_mon_shared/storage',
      help='url (including file://) to post monitoring metrics to.'
           ' (default: %(default)s)')
    parser.add_argument(
      '--ts-mon-flush-interval-secs',
      type=int,
      default=60,
      help=('automatically push metrics on this interval if '
            '--ts-mon-flush=auto.'))
   # ... other arguments below ...
