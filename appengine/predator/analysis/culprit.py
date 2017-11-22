# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from collections import namedtuple


class Culprit(namedtuple('Culprit',
    ['project', 'components', 'suspected_cls',
     'regression_range', 'algorithm'])):
  """The result of successfully identifying the culprit of a crash report.

  That is, this is what ``Predator.FindCultprit`` returns. It encapsulates
  all the information predator discovered during its various analyses.

  Args:
    project (str): the most-suspected project
    components (list of str): the suspected crbug components.
    suspected_cls (list of Suspects): the suspected suspected_cls.
    regression_range (tuple): a pair of the last-good and first-bad versions.
    algorithm (str): What algorithm was used to produce this object.
    log (dict): Provide information to explain the results, the log is
      usually warning or error log to explain why we didn't find valid
      results.for example, if the crash doesn't have regression range,
      the log will explain that there is no suspected cl due to lack of
      regression_range.
  """
  __slots__ = ()

  def __new__(cls, project, components, suspected_cls, regression_range,
              algorithm):
    return super(cls, Culprit).__new__(cls, project, components, suspected_cls,
                                       regression_range, algorithm)

  @property
  def fields(self):
    return self._fields

  # TODO(http://crbug/644476): better name for this method.
  def ToDicts(self):
    """Convert this object to a pair of anonymous dicts for JSON.

    Returns:
      (analysis_result_dict, tag_dict)
      The analysis result is a dict like below:
      {
          # Indicate if Predator found any suspects_cls, project,
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
                  "reasons": [('MinDistance', 1, 'minimum distance is 0.'),
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
      for query and monitoring purpose on Predator side. For allowed keys,
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
    result = {}
    result['found'] = (
        bool(self.project) or
        bool(self.components) or
        bool(self.suspected_cls) or
        bool(self.regression_range))
    if self.regression_range:
      result['regression_range'] = self.regression_range
    if self.project:
      result['suspected_project'] = self.project
    if self.components:
      result['suspected_components'] = self.components
    if self.suspected_cls:
      result['suspected_cls'] = [cl.ToDict() for cl in self.suspected_cls]

    tags = {
      'found_suspects': bool(self.suspected_cls),
      'has_regression_range': bool(self.regression_range),
      'found_project': bool(self.project),
      'found_components': bool(self.components),
      'solution': self.algorithm,
    }

    return result, tags
