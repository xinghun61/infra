# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb

from gae_libs.gitiles.cached_gitiles_repository import CachedGitilesRepository
from gae_libs.http.http_client_appengine import HttpClientAppengine
from gae_libs.pipeline_wrapper import BasePipeline
from waterfall import extractor_util
from waterfall.flake import heuristic_analysis_util


class IdentifySuspectedRevisionsPipeline(BasePipeline):
  """Generates suspected CLs for flake analysis."""

  GIT_REPO = CachedGitilesRepository(
      HttpClientAppengine(),
      'https://chromium.googlesource.com/chromium/src.git')

  # Arguments number differs from overridden method - pylint: disable=W0221
  def run(self, analysis_urlsafe_key, test_location):
    """Pipeline to determine heuristic results for a flake analysis.

    Args:
      analysis_urlsafe_key (str): The url-safe key to the MasterFlakeAnalysis.
      test_location (dict): Dict of the test's location in the format:
      {
          'line': (int),
          'file': (str)
      }

    Returns:
      A list of revision tuples as output by _GenerateSuspectedRanges().
    """
    analysis = ndb.Key(urlsafe=analysis_urlsafe_key).get()
    assert analysis
    suspected_build_point = analysis.GetDataPointOfSuspectedBuild()
    assert suspected_build_point

    file_path = test_location.get('file')
    if not file_path:
      return []

    file_path = extractor_util.NormalizeFilePath(file_path)
    git_blame = self.GIT_REPO.GetBlame(file_path,
                                       suspected_build_point.git_hash)
    blame_list = suspected_build_point.blame_list
    suspected_revisions = heuristic_analysis_util.GetSuspectedRevisions(
        git_blame, blame_list)
    heuristic_analysis_util.SaveFlakeCulpritsForSuspectedRevisions(
        self.GIT_REPO, analysis_urlsafe_key, suspected_revisions)

    return heuristic_analysis_util.GenerateSuspectedRanges(
        suspected_revisions, blame_list)
