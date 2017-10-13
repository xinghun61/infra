# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""A servlet that implements the backend of issues search.

The GET request to a backend search has the same query string
parameters as the issue list servlet.  But, instead of rendering a
HTML page, the backend search handler returns a JSON response with a
list of matching, sorted issue IID numbers from this shard that are
viewable by the requesting user.

Each backend search request works within a single shard.  Each
besearch backend job can access any single shard while processing a request.

The current user ID must be passed in from the frontend for permission
checking.  The user ID for the special "me" term can also be passed in
(so that you can view another user's dashboard and "me" will refer to
them).
"""

import logging
import time

from framework import jsonfeed
from search import backendsearchpipeline
from tracker import tracker_constants


class BackendSearch(jsonfeed.InternalTask):
  """JSON servlet for issue search in a GAE backend."""

  CHECK_SAME_APP = True
  _DEFAULT_RESULTS_PER_PAGE = tracker_constants.DEFAULT_RESULTS_PER_PAGE

  def HandleRequest(self, mr):
    """Search for issues and respond with the IIDs of matching issues.

    Args:
      mr: common information parsed from the HTTP request.

    Returns:
      Results dictionary in JSON format.
    """
    # Users are never logged into backends, so the frontends tell us.
    logging.info('query_project_names is %r', mr.query_project_names)
    pipeline = backendsearchpipeline.BackendSearchPipeline(
        mr, self.services, self._DEFAULT_RESULTS_PER_PAGE,
        mr.query_project_names, mr.specified_logged_in_user_id,
        mr.specified_me_user_id)
    pipeline.SearchForIIDs()

    start = time.time()
    # Backends work in parallel to precache issues that the
    # frontend is very likely to need.
    _prefetched_issues = self.services.issue.GetIssues(
        mr.cnxn, pipeline.result_iids[:mr.start + mr.num],
        shard_id=mr.shard_id)
    logging.info('prefetched and memcached %d issues in %d ms',
                 len(pipeline.result_iids[:mr.start + mr.num]),
                 int(1000 * (time.time() - start)))

    if pipeline.error:
      error_message = pipeline.error.message
    else:
      error_message = None

    return {
        'unfiltered_iids': pipeline.result_iids,
        'search_limit_reached': pipeline.search_limit_reached,
        'error': error_message,
    }
