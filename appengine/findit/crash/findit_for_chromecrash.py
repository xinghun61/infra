# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
from collections import namedtuple

from common import chromium_deps
from crash import detect_regression_range
from crash import findit_for_crash
from crash.chromecrash_parser import ChromeCrashParser
from crash.project_classifier import ProjectClassifier
from crash.component_classifier import Component
from crash.component_classifier import ComponentClassifier
from model.crash.crash_config import CrashConfig

# TODO(katesonia): Remove the default value after adding validity check to
# config.
_DEFAULT_TOP_N = 7


# TODO(wrengr): move this to its own file, so it can be shared. When we do
# so, we'll need to also pass in the 'solution' argument for the tag_dict.
class Culprit(namedtuple('Culprit',
    ['project', 'components', 'cls', 'regression_range'])):

  # TODO(wrengr): better name for this method.
  def ToDicts(self):
    """Convert this object to a pair of anonymous dicts for JSON.

    Returns:
      (analysis_result_dict, tag_dict)
      The analysis result is a dict like below:
      {
          # Indicate if Findit found any suspects_cls, project,
          # components or regression_range.
          "found": true,
          "suspected_project": "chromium-v8", # Which project is most suspected.
          "feedback_url": "https://.."
          "suspected_cls": [
              {
                  "revision": "commit-hash",
                  "url": "https://chromium.googlesource.com/chromium/src/+/...",
                  "review_url": "https://codereview.chromium.org/issue-number",
                  "project_path": "third_party/pdfium",
                  "author": "who@chromium.org",
                  "time": "2015-08-17 03:38:16",
                  "reason": "a plain string with '\n' as line break to expla..."
                  "reason": [('MinDistance', 1, 'minimum distance is 0.'),
                             ('TopFrame', 0.9, 'top frame is2nd frame.')],
                  "changed_files": [
                      {"file": "file_name1.cc",
                       "blame_url": "https://...",
                       "info": "minimum distance (LOC) 0, frame #2"},
                      {"file": "file_name2.cc",
                       "blame_url": "https://...",
                       "info": "minimum distance (LOC) 20, frame #4"},
                      ...
                  ],
                  "confidence": 0.60
              },
              ...,
          ],
          "regression_range": [  # Detected regression range.
              "53.0.2765.0",
              "53.0.2766.0"
          ],
          "suspected_components": [  # A list of crbug components to file bugs.
              "Blink>JavaScript"
          ]
      }

      The code review url might not always be available, because not all
      commits go through code review. In that case, commit url should
      be used instead.

      The tag dict are allowed key/value pairs to tag the analysis result
      for query and monitoring purpose on Findit side. For allowed keys,
      please refer to crash_analysis.py and fracas_crash_analysis.py:
        For results with normal culprit-finding algorithm: {
            'found_suspects': True,
            'has_regression_range': True,
            'solution': 'core_algorithm',
        }
        For results using git blame without a regression range: {
            'found_suspects': True,
            'has_regression_range': False,
            'solution': 'blame',
        }
        If nothing is found: {
            'found_suspects': False,
        }
    """
    cls_list = [result.ToDict() for result in self.cls]

    # TODO(wrengr): reformulate the JSON stuff so we can drop fields which
    # are empty; so that, in turn, we can get rid of the NullCulprit class.
    return (
        {
          'found': (bool(self.project) or
                    bool(self.components) or
                    bool(cls_list) or
                    bool(self.regression_range)),
          'regression_range': self.regression_range,
          'suspected_project': self.project,
          'suspected_components': self.components,
          'suspected_cls': cls_list,
        },
        {
          'found_suspects': bool(cls_list),
          'found_project': bool(self.project),
          'found_components': bool(self.components),
          'has_regression_range': bool(self.regression_range),
          'solution': 'core_algorithm',
        }
      )


# TODO(wrengr): Either (a) reformulate the unit tests so that FindCulprit
# can, in fact, return None; or else (b) reformulate the JSON stuff so
# that the various fields are optional, so that we can just use
# Culprit('', [], [], None) directly.
class NullCulprit(object):
  """A helper class so FindCulprit doesn't return None.

  This class is analogous to Culprit(None, [], [], None), except that the
  result of the ToDicts method is more minimalistic."""

  def ToDicts(self):
    return (
        {'found': False},
        {'found_suspects': False,
         'has_regression_range': False}
    )


# TODO(wrengr): better name for this class. Given the "findit_for_*.py"
# file names, one might suspect that each of those files implements
# something analogous to this file, and hence we could make a superclass
# to factor out the common bits. However, in truth, all those files
# are unrelated and do completely different things.
class FinditForChromeCrash(object):
  """Process crashes from Chrome crash server and find culprits for them.

  Even though this class has only one method, it is helpful because it
  allows us to cache things which should outlive each call to that method.
  For example, we store a single ComponentClassifier object so that we
  only compile the regexes for each Component object once, rather than
  doing so on each call to FindCulprit. In addition, the class lets
  us cache various configuration options so that we need not depend
  on CrashConfig; thereby decoupling the analysis itself from UX concerns
  about deciding how to run those analyses.
  """
  # TODO(wrengr): remove the dependency on CrashConfig entirely, by
  # passing the relevant data as arguments to this constructor.
  def __init__(self):
    crash_config = CrashConfig.Get()
    component_classifier_config = crash_config.component_classifier

    # TODO(wrengr): why are these two different?
    component_classifier_top_n = component_classifier_config['top_n']
    self._fracas_top_n = crash_config.fracas.get('top_n', _DEFAULT_TOP_N)

    self.component_classifier = ComponentClassifier(
        [Component(component_name, path_regex, function_regex)
          for path_regex, function_regex, component_name
          in component_classifier_config['path_function_component']],
        component_classifier_top_n)

    # TODO(wrengr); fix ProjectClassifier so it doesn't depend on CrashConfig.
    self.project_classifier = ProjectClassifier()

  # TODO(wrengr): since this is the only method of interest, it would
  # be better IMO to rename it to __call__ to reduce verbosity.
  def FindCulprit(self, signature, platform, stack_trace, crashed_version,
                  regression_range):
    """Finds culprits for a Chrome crash.

    Args:
      signature (str): The signature of a crash on the Chrome crash server.
      platform (str): The platform name, could be 'win', 'mac', 'linux',
        'android', 'ios', etc.
      stack_trace (str): A string containing the stack trace of a crash.
      crashed_version (str): The version of Chrome in which the crash occurred.
      regression_range (list or None): [good_version, bad_revision] or None.

    Returns:
      A Culprit object.
    """
    crash_deps = chromium_deps.GetChromeDependency(crashed_version, platform)
    stacktrace = ChromeCrashParser().Parse(stack_trace, crash_deps, signature)
    if not stacktrace:
      logging.warning('Failed to parse the stacktrace %s', stack_trace)
      # TODO(wrengr): refactor things so we don't need the NullCulprit class.
      return NullCulprit()

    # Get regression deps and crash deps.
    regression_deps_rolls = {}
    if regression_range:
      last_good_version, first_bad_version = regression_range
      logging.info('Find regression range %s:%s', last_good_version,
                   first_bad_version)
      regression_deps_rolls = chromium_deps.GetDEPSRollsDict(
          last_good_version, first_bad_version, platform)

    suspected_cls = findit_for_crash.FindItForCrash(
        stacktrace, regression_deps_rolls, crash_deps, self._fracas_top_n)

    crash_stack = stacktrace.crash_stack
    suspected_project = self.project_classifier.Classify(
        suspected_cls, crash_stack)

    suspected_components = self.component_classifier.Classify(
        suspected_cls, crash_stack)

    return Culprit(suspected_project, suspected_components, suspected_cls,
        regression_range)
