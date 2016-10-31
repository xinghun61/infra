# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from collections import namedtuple

# TODO(http://crbug.com/659346): We do call this code from various
# unittests, just not from culprit_test.py; so we need to add some extra
# unittests there.
class Culprit(namedtuple('Culprit',
    ['project', 'components', 'cls', 'regression_range', 'algorithm']
    )): # pragma: no cover
  """The result of successfully identifying the culprit of a crash report.
  
  Args:
    project (str): the most-suspected project
    components (list of str): the suspected crbug components.
    cls (list of ??): the suspected CLs.
    regression_range (tuple): a pair of the last-good and first-bad versions.
    algorithm (str): What algorithm was used to produce this object.
  """
  __slots__ = ()

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
    # TODO(http://crbug.com/644411): reformulate the JSON stuff so we
    # can drop fields which are empty; so that, in turn, we can get rid
    # of the NullCulprit class.
    return (
        {
          'found': (bool(self.project) or
                    bool(self.components) or
                    bool(self.cls) or
                    bool(self.regression_range)),
          'regression_range': self.regression_range,
          'suspected_project': self.project,
          'suspected_components': self.components,
          'suspected_cls': [cl.ToDict() for cl in self.cls],
        },
        {
          'found_suspects': bool(self.cls),
          'found_project': bool(self.project),
          'found_components': bool(self.components),
          'has_regression_range': bool(self.regression_range),
          'solution': self.algorithm,
        }
      )


# TODO(http://crbug.com/659346): We do call this code from various
# unittests, just not from culprit_test.py; so we need to add some extra
# unittests there.
# TODO(http://crbug.com/659359): eliminate the need for this class.
class NullCulprit(object): # pragma: no cover
  """The result of failing to identify the culprit of a crash report.

  This class serves as a helper so that we can avoid returning None. It
  has all the same properties and methods as the Culprit class, but
  returns the empty string, the empty list, or None, as appropriate. The
  main difference compared to using Culprit with all those falsy values
  is that the result of the ToDicts method is more minimalistic.

  Ideally we'd like to be able to refactor things to avoid the need
  for this class. Mostly that means (1) refactoring the unittests to
  allow ``Findit.FindCulprit`` to return None, and (2) reformulating
  ``Culprit.ToDicts`` to create minimal dicts and reformulating the JSON
  protocol to support that.
  """
  __slots__ = ()

  @property
  def fields(self):
    raise NotImplementedError()

  @property
  def project(self):
    return ''

  @property
  def components(self):
    return []

  @property
  def cls(self):
    return []

  @property
  def regression_range(self):
    return None

  @property
  def algorithm(self):
    return None

  def ToDicts(self):
    return (
        {'found': False},
        {'found_suspects': False,
         'has_regression_range': False}
    )
