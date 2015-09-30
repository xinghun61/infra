# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Main implementation of metric_tool."""

import ast
import os
import logging


# https://chromium.googlesource.com/infra/infra/+/master/infra_libs/logs/README.md
LOGGER = logging.getLogger(__name__)

METRICS_NAMES = set(('StringMetric', 'BooleanMetric',
                     'CounterMetric', 'GaugeMetric', 'CumulativeMetric',
                     'FloatMetric', 'CumulativeDistributionMetric',
                     'NonCumulativeDistributionMetric'))


def extract_metrics_descriptions(filepath):
  """Parse a python file and return all metrics descriptions it can find.

  A metric description is the value of the 'description' keyword passed to a
  metric definition (classes deriving from ts_mon.Metric)

  Args:
    filepath (str): path to a Python file.

  Returns:
    description (list of tuples): each tuple being
       (metric name, description string). Metric name is 'DYNAMIC' it something
       different than a static string is used in the metric creation.
       If a metric is instanciated without a description, return None.
  """
  descriptions = []
  try:
    with open(filepath, 'r') as f:
      content = f.read()  # pragma: no branch
  except IOError:
    return descriptions

  try:
    root = ast.parse(content)
  except SyntaxError:  # just ignore invalid / python3 files.
    return descriptions

  for node in ast.walk(root):
    if not isinstance(node, ast.Call):
      continue

    # Look for metrics definitions
    calls = []
    if isinstance(node.func, ast.Name):
      if node.func.id in METRICS_NAMES:
        LOGGER.debug('Method %s found line %d', node.func.id, node.func.lineno)
        calls.append(node)
    elif isinstance(node.func, ast.Attribute):  # pragma: no branch
      if node.func.attr in METRICS_NAMES:
        LOGGER.debug('Method %s found line %d',
                     node.func.attr, node.func.lineno)
        calls.append(node)

    # Extract parameters from function call
    for fcall in calls:
      # Metric name
      metric_name = 'DYNAMIC'
      if fcall.args and isinstance(fcall.args[0], ast.Str):
        metric_name = fcall.args[0].s

      # Getting descriptions
      description = None
      for keyword in fcall.keywords:
        if keyword.arg == 'description' and isinstance(keyword.value, ast.Str):
          description = keyword.value.s

      descriptions.append((filepath, fcall.lineno, metric_name, description))

  return descriptions


def main(path):
  """Recursively walk a directory structure and print metrics documentation.

  For all instanciated metrics in any Python file found under the directory
  passed as argument, if a 'description' keyword is provided print it
  alongside the metric name.

  Args:
    path (str): directory.
  """
  documented = []
  non_documented = []

  for (dirpath, _, filenames) in os.walk(path):
    for filename in filenames:

      if (not filename.endswith('.py')  # pragma: no branch
          or filename.endswith('_test.py')):
        continue  # pragma: no cover

      full_filename = os.path.join(dirpath, filename)
      LOGGER.debug('Scanning file %s', full_filename)
      descriptions = extract_metrics_descriptions(full_filename)

      for description in descriptions:
        # TODO(pgervais): use namedtuple here instead
        if description[3]:
          documented.append(description)
        else:
          non_documented.append(description)

  if documented:  # pragma: no branch
    print('\nDocumented metrics found:')
    for description in documented:
      print('/chrome/infra/{2} \t"{3}" at {0}:{1}'.format(*description))

  if non_documented:  # pragma: no branch
    print('\nUndocumented metrics found:')
    for description in non_documented:
      print('/chrome/infra/{2} \t at {0}:{1}'.format(*description))
