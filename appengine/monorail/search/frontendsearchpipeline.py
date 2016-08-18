# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""The FrontendSearchPipeline class manages issue search and sorting.

The frontend pipeline checks memcache for cached results in each shard.  It
then calls backend jobs to do any shards that had a cache miss.  On cache hit,
the cached results must be filtered by permissions, so the at-risk cache and
backends are consulted.  Next, the sharded results are combined into an overall
list of IIDs.  Then, that list is paginated and the issues on the current
pagination page can be shown.  Alternatively, this class can determine just the
position the currently shown issue would occupy in the overall sorted list.
"""

import json

import collections
import logging
import math
import random
import time

from google.appengine.api import apiproxy_stub_map
from google.appengine.api import memcache
from google.appengine.api import modules
from google.appengine.api import urlfetch

import settings
from features import savedqueries_helpers
from framework import framework_constants
from framework import framework_helpers
from framework import paginate
from framework import sorting
from framework import urls
from search import query2ast
from search import searchpipeline
from services import fulltext_helpers
from tracker import tracker_bizobj
from tracker import tracker_constants
from tracker import tracker_helpers


# Fail-fast responses usually finish in less than 50ms.  If we see a failure
# in under that amount of time, we don't bother logging it.
FAIL_FAST_LIMIT_SEC = 0.050

# The choices help balance the cost of choosing samples vs. the cost of
# selecting issues that are in a range bounded by neighboring samples.
# Preferred chunk size parameters were determined by experimentation.
MIN_SAMPLE_CHUNK_SIZE = int(
    math.sqrt(tracker_constants.DEFAULT_RESULTS_PER_PAGE))
MAX_SAMPLE_CHUNK_SIZE = int(math.sqrt(settings.search_limit_per_shard))
PREFERRED_NUM_CHUNKS = 50


class FrontendSearchPipeline(object):
  """Manage the process of issue search, including backends and caching.

  Even though the code is divided into several methods, the public
  methods should be called in sequence, so the execution of the code
  is pretty much in the order of the source code lines here.
  """

  def __init__(self, mr, services, prof, default_results_per_page):
    self.mr = mr
    self.services = services
    self.profiler = prof
    self.default_results_per_page = default_results_per_page
    self.grid_mode = (mr.mode == 'grid')
    self.grid_limited = False
    self.pagination = None
    self.num_skipped_at_start = 0
    self.total_count = 0

    self.query_project_names = set()
    if mr.query_project_names:
      self.query_project_names.update(mr.query_project_names)

    projects = services.project.GetProjectsByName(
        mr.cnxn, self.query_project_names).values()
    self.query_project_ids = [p.project_id for p in projects]
    if mr.project_name:
      self.query_project_ids.append(mr.project_id)
      self.query_project_names.add(mr.project_name)

    config_dict = self.services.config.GetProjectConfigs(
        mr.cnxn, self.query_project_ids)
    self.harmonized_config = tracker_bizobj.HarmonizeConfigs(
        config_dict.values())

    # The following fields are filled in as the pipeline progresses.
    # The value None means that we still need to compute that value.
    self.users_by_id = {}
    self.nonviewable_iids = {}  # {shard_id: set(iid)}
    self.unfiltered_iids = {}  # {shard_id: [iid, ...]} needing perm checks.
    self.filtered_iids = {}  # {shard_id: [iid, ...]} already perm checked.
    self.search_limit_reached = {}  # {shard_id: [bool, ...]}.
    self.counts = {}
    self.allowed_iids = []  # Matching iids that user is permitted to view.
    self.allowed_results = None  # results that the user is permitted to view.
    self.visible_results = None  # allowed_results on current pagination page.
    self.error_responses = set()

    # Projects that contain the result issues.  This starts off as a dict of
    # all the query projects, but it can grow based on the found issues in the
    # case where the user is searching across the entire site.
    self.issue_projects = {p.project_id: p for p in projects}

    error_msg = query2ast.CheckSyntax(
        self.mr.query, self.harmonized_config, warnings=self.mr.warnings)
    if error_msg:
      self.mr.errors.query = error_msg

  def SearchForIIDs(self):
    """Use backends to search each shard and store their results."""
    with self.profiler.Phase('Checking cache and calling Backends'):
      rpc_tuples = _StartBackendSearch(
          self.mr, self.query_project_names, self.query_project_ids,
          self.harmonized_config, self.unfiltered_iids,
          self.search_limit_reached, self.nonviewable_iids,
          self.error_responses, self.services)

    with self.profiler.Phase('Waiting for Backends'):
      try:
        _FinishBackendSearch(rpc_tuples)
      except Exception as e:
        logging.exception(e)
        raise

    if self.error_responses:
      logging.error('%r error responses. Incomplete search results.',
                    self.error_responses)

    with self.profiler.Phase('Filtering cached results'):
      for shard_id in self.unfiltered_iids:
        if shard_id not in self.nonviewable_iids:
          logging.error(
            'Not displaying shard %r because of no nonviewable_iids', shard_id)
          self.error_responses.add(shard_id)
          filtered_shard_iids = []
        else:
          unfiltered_shard_iids = self.unfiltered_iids[shard_id]
          nonviewable_shard_iids = self.nonviewable_iids[shard_id]
          # TODO(jrobbins): avoid creating large temporary lists.
          filtered_shard_iids = [iid for iid in unfiltered_shard_iids
                                 if iid not in nonviewable_shard_iids]
        if self.grid_mode:
          self.filtered_iids[shard_id] = filtered_shard_iids
        else:
          self.filtered_iids[shard_id] = filtered_shard_iids[
              :self.mr.start + self.mr.num]
        self.counts[shard_id] = len(filtered_shard_iids)

    with self.profiler.Phase('Counting all filtered results'):
      self.total_count = sum(self.counts.itervalues())

  def MergeAndSortIssues(self):
    """Merge and sort results from all shards into one combined list."""
    with self.profiler.Phase('selecting issues to merge and sort'):
      if not self.grid_mode:
        self._NarrowFilteredIIDs()
      self.allowed_iids = []
      for filtered_shard_iids in self.filtered_iids.itervalues():
        self.allowed_iids.extend(filtered_shard_iids)

    # The grid view is not paginated, so limit the results shown to avoid
    # generating a HTML page that would be too large.
    limit = settings.max_issues_in_grid
    if self.grid_mode and len(self.allowed_iids) > limit:
      self.grid_limited = True
      self.allowed_iids = self.allowed_iids[:limit]

    with self.profiler.Phase('getting allowed results'):
      self.allowed_results = self.services.issue.GetIssues(
          self.mr.cnxn, self.allowed_iids)

    # Note: At this point, we have results that are only sorted within
    # each backend's shard. We still need to sort the merged result.
    self._LookupNeededUsers(self.allowed_results)
    with self.profiler.Phase('merging and sorting issues'):
      self.allowed_results = _SortIssues(
          self.mr, self.allowed_results, self.harmonized_config,
          self.users_by_id)

  def _NarrowFilteredIIDs(self):
    """Combine filtered shards into a range of IIDs for issues to sort.

    The niave way is to concatenate shard_iids[:start + num] for all
    shards then select [start:start + num].  We do better by sampling
    issues and then determining which of those samples are known to
    come before start or after start+num.  We then trim off all those IIDs
    and sort a smaller range of IIDs that might actuall be displayed.
    See the design doc at go/monorail-sorting.

    This method modifies self.fitered_iids and self.num_skipped_at_start.
    """
    # Sample issues and skip those that are known to come before start.
    # See the "Sorting in Monorail" design doc.

    # If the result set is small, don't bother optimizing it.
    orig_length = _TotalLength(self.filtered_iids)
    if orig_length < self.mr.num * 4:
      return

    # 1. Get sample issues in each shard and sort them all together.
    last = self.mr.start + self.mr.num
    on_hand_samples = {}
    needed_iids = []
    for shard_id in self.filtered_iids:
      self._AccumulateSampleIssues(
          self.filtered_iids[shard_id], on_hand_samples, needed_iids)
    retrieved_samples = self.services.issue.GetIssuesDict(
        self.mr.cnxn, needed_iids)
    sample_issues = on_hand_samples.values() + retrieved_samples.values()
    self._LookupNeededUsers(sample_issues)
    sample_issues = _SortIssues(
        self.mr, sample_issues, self.harmonized_config, self.users_by_id)
    sample_iids = [issue.issue_id for issue in sample_issues]

    # 2. Trim off some IIDs that are sure to be positioned after last.
    num_trimmed_end = _TrimEndShardedIIDs(self.filtered_iids, sample_iids, last)
    logging.info('Trimmed %r issues from the end of shards', num_trimmed_end)

    # 3. Trim off some IIDs that are sure to be posiitoned before start.
    keep = _TotalLength(self.filtered_iids) - self.mr.start
    # Reverse the sharded lists.
    _ReverseShards(self.filtered_iids)
    sample_iids.reverse()
    self.num_skipped_at_start = _TrimEndShardedIIDs(
        self.filtered_iids, sample_iids, keep)
    logging.info('Trimmed %r issues from the start of shards',
                 self.num_skipped_at_start)
    # Reverse sharded lists again to get back into forward order.
    _ReverseShards(self.filtered_iids)

  def DetermineIssuePosition(self, issue):
    """Calculate info needed to show the issue flipper.

    Args:
      issue: The issue currently being viewed.

    Returns:
      A 3-tuple (prev_iid, index, next_iid) were prev_iid is the
      IID of the previous issue in the total ordering (or None),
      index is the index that the current issue has in the total
      ordering, and next_iid is the next issue (or None).  If the current
      issue is not in the list of results at all, returns None, None, None.
    """
    # 1. If the current issue is not in the results at all, then exit.
    if not any(issue.issue_id in filtered_shard_iids
               for filtered_shard_iids in self.filtered_iids.itervalues()):
      return None, None, None

    # 2. Choose and retrieve sample issues in each shard.
    samples_by_shard = {}  # {shard_id: {iid: issue}}
    needed_iids = []
    for shard_id in self.filtered_iids:
      samples_by_shard[shard_id] = {}
      self._AccumulateSampleIssues(
          self.filtered_iids[shard_id], samples_by_shard[shard_id], needed_iids)
    retrieved_samples = self.services.issue.GetIssuesDict(
        self.mr.cnxn, needed_iids)
    for retrieved_iid, retrieved_issue in retrieved_samples.iteritems():
      shard_id = retrieved_iid % settings.num_logical_shards
      samples_by_shard[shard_id][retrieved_iid] = retrieved_issue

    # 3. Build up partial results for each shard.
    preceeding_counts = {}  # dict {shard_id: num_issues_preceeding_current}
    prev_candidates, next_candidates = [], []
    for shard_id in self.filtered_iids:
      prev_candidate, index_in_shard, next_candidate = (
          self._DetermineIssuePositionInShard(
              shard_id, issue, samples_by_shard[shard_id]))
      preceeding_counts[shard_id] = index_in_shard
      if prev_candidate:
        prev_candidates.append(prev_candidate)
      if next_candidate:
        next_candidates.append(next_candidate)

    # 4. Combine the results.
    index = sum(preceeding_counts.itervalues())
    prev_candidates = _SortIssues(
        self.mr, prev_candidates, self.harmonized_config, self.users_by_id)
    prev_iid = prev_candidates[-1].issue_id if prev_candidates else None
    next_candidates = _SortIssues(
        self.mr, next_candidates, self.harmonized_config, self.users_by_id)
    next_iid = next_candidates[0].issue_id if next_candidates else None

    return prev_iid, index, next_iid

  def _DetermineIssuePositionInShard(self, shard_id, issue, sample_dict):
    """Determine where the given issue would fit into results from a shard."""
    # See the design doc for details.  Basically, it first surveys the results
    # to bound a range where the given issue would belong, then it fetches the
    # issues in that range and sorts them.

    filtered_shard_iids = self.filtered_iids[shard_id]

    # 1. Select a sample of issues, leveraging ones we have in RAM already.
    issues_on_hand = sample_dict.values()
    if issue.issue_id not in sample_dict:
      issues_on_hand.append(issue)

    self._LookupNeededUsers(issues_on_hand)
    sorted_on_hand = _SortIssues(
        self.mr, issues_on_hand, self.harmonized_config, self.users_by_id)
    sorted_on_hand_iids = [soh.issue_id for soh in sorted_on_hand]
    index_in_on_hand = sorted_on_hand_iids.index(issue.issue_id)

    # 2. Bound the gap around where issue belongs.
    if index_in_on_hand == 0:
      fetch_start = 0
    else:
      prev_on_hand_iid = sorted_on_hand_iids[index_in_on_hand - 1]
      fetch_start = filtered_shard_iids.index(prev_on_hand_iid) + 1

    if index_in_on_hand == len(sorted_on_hand) - 1:
      fetch_end = len(filtered_shard_iids)
    else:
      next_on_hand_iid = sorted_on_hand_iids[index_in_on_hand + 1]
      fetch_end = filtered_shard_iids.index(next_on_hand_iid)

    # 3. Retrieve all the issues in that gap to get an exact answer.
    fetched_issues = self.services.issue.GetIssues(
        self.mr.cnxn, filtered_shard_iids[fetch_start:fetch_end])
    if issue.issue_id not in filtered_shard_iids[fetch_start:fetch_end]:
      fetched_issues.append(issue)
    self._LookupNeededUsers(fetched_issues)
    sorted_fetched = _SortIssues(
        self.mr, fetched_issues, self.harmonized_config, self.users_by_id)
    sorted_fetched_iids = [sf.issue_id for sf in sorted_fetched]
    index_in_fetched = sorted_fetched_iids.index(issue.issue_id)

    # 4. Find the issues that come immediately before and after the place where
    # the given issue would belong in this shard.
    if index_in_fetched > 0:
      prev_candidate = sorted_fetched[index_in_fetched - 1]
    elif index_in_on_hand > 0:
      prev_candidate = sorted_on_hand[index_in_on_hand - 1]
    else:
      prev_candidate = None

    if index_in_fetched < len(sorted_fetched) - 1:
      next_candidate = sorted_fetched[index_in_fetched + 1]
    elif index_in_on_hand < len(sorted_on_hand) - 1:
      next_candidate = sorted_on_hand[index_in_on_hand + 1]
    else:
      next_candidate = None

    return prev_candidate, fetch_start + index_in_fetched, next_candidate

  def _AccumulateSampleIssues(self, issue_ids, sample_dict, needed_iids):
    """Select a scattering of issues from the list, leveraging RAM cache."""
    chunk_size = max(MIN_SAMPLE_CHUNK_SIZE, min(MAX_SAMPLE_CHUNK_SIZE,
        int(len(issue_ids) / PREFERRED_NUM_CHUNKS)))
    for i in range(chunk_size, len(issue_ids), chunk_size):
      issue = self.services.issue.GetAnyOnHandIssue(
          issue_ids, start=i, end=min(i + chunk_size, len(issue_ids)))
      if issue:
        sample_dict[issue.issue_id] = issue
      else:
        needed_iids.append(issue_ids[i])

  def _LookupNeededUsers(self, issues):
    """Look up user info needed to sort issues, if any."""
    with self.profiler.Phase('lookup of owner, reporter, and cc'):
      additional_user_views_by_id = (
          tracker_helpers.MakeViewsForUsersInIssues(
              self.mr.cnxn, issues, self.services.user,
              omit_ids=self.users_by_id.keys()))
      self.users_by_id.update(additional_user_views_by_id)

  def Paginate(self):
    """Fetch matching issues and paginate the search results.

    These two actions are intertwined because we try to only
    retrieve the Issues on the current pagination page.
    """
    if self.grid_mode:
      # We don't paginate the grid view.  But, pagination object shows counts.
      self.pagination = paginate.ArtifactPagination(
          self.mr, self.allowed_results, self.default_results_per_page,
          total_count=self.total_count, list_page_url=urls.ISSUE_LIST)
      # We limited the results, but still show the original total count.
      self.visible_results = self.allowed_results

    else:
      # We already got the issues, just display a slice of the visible ones.
      limit_reached = False
      for shard_limit_reached in self.search_limit_reached.values():
        limit_reached |= shard_limit_reached
      self.pagination = paginate.ArtifactPagination(
          self.mr, self.allowed_results, self.default_results_per_page,
          total_count=self.total_count, list_page_url=urls.ISSUE_LIST,
          limit_reached=limit_reached, skipped=self.num_skipped_at_start)
      self.visible_results = self.pagination.visible_results

    # If we were not forced to look up visible users already, do it now.
    if self.grid_mode:
      self._LookupNeededUsers(self.allowed_results)
    else:
      self._LookupNeededUsers(self.visible_results)

  def __repr__(self):
    """Return a string that shows the internal state of this pipeline."""
    if self.allowed_iids:
      shown_allowed_iids = self.allowed_iids[:200]
    else:
      shown_allowed_iids = self.allowed_iids

    if self.allowed_results:
      shown_allowed_results = self.allowed_results[:200]
    else:
      shown_allowed_results = self.allowed_results

    parts = [
        'allowed_iids: %r' % shown_allowed_iids,
        'allowed_results: %r' % shown_allowed_results,
        'len(visible_results): %r' % (
            self.visible_results and len(self.visible_results))]
    return '%s(%s)' % (self.__class__.__name__, '\n'.join(parts))


def _MakeBackendCallback(func, *args):
  return lambda: func(*args)


def _StartBackendSearch(
    mr, query_project_names, query_project_ids, harmonized_config,
    unfiltered_iids_dict, search_limit_reached_dict,
    nonviewable_iids, error_responses, services):
  """Request that our backends search and return a list of matching issue IDs.

  Args:
    mr: commonly used info parsed from the request, including query and
        sort spec.
    query_project_names: set of project names to search.
    query_project_ids: list of project IDs to search.
    harmonized_config: combined ProjectIssueConfig for all projects being
        searched.
    unfiltered_iids_dict: dict {shard_id: [iid, ...]} of unfiltered search
        results to accumulate into.  They need to be later filtered by
        permissions and merged into filtered_iids_dict.
    search_limit_reached_dict: dict{shard_id: [bool, ...]} to determine if
        the search limit of any shard was reached.
    nonviewable_iids: dict {shard_id: set(iid)} of restricted issues in the
        projects being searched that the signed in user cannot view.
    services: connections to backends.

  Returns:
    A list of rpc_tuples that can be passed to _FinishBackendSearch to wait
    on any remaining backend calls.

  SIDE-EFFECTS:
    Any data found in memcache is immediately put into unfiltered_iids_dict.
    As the backends finish their work, _HandleBackendSearchResponse will update
    unfiltered_iids_dict for those shards.
  """
  rpc_tuples = []
  needed_shard_ids = set(range(settings.num_logical_shards))

  # 1. Get whatever we can from memcache.  Cache hits are only kept if they are
  # not already expired.  Each kept cache hit will have unfiltered IIDs, so we
  # need to get the at-risk IIDs to efficiently filter them based on perms.
  project_shard_timestamps = _GetProjectTimestamps(
      query_project_ids, needed_shard_ids)

  if mr.use_cached_searches:
    cached_unfiltered_iids_dict, cached_search_limit_reached_dict = (
        _GetCachedSearchResults(
            mr, query_project_ids, needed_shard_ids, harmonized_config,
            project_shard_timestamps, services))
    unfiltered_iids_dict.update(cached_unfiltered_iids_dict)
    search_limit_reached_dict.update(cached_search_limit_reached_dict)
  for cache_hit_shard_id in unfiltered_iids_dict:
    needed_shard_ids.remove(cache_hit_shard_id)

  _GetNonviewableIIDs(
    query_project_ids, mr.auth.user_id, set(range(settings.num_logical_shards)),
    rpc_tuples, nonviewable_iids, project_shard_timestamps,
    services.cache_manager.processed_invalidations_up_to,
    mr.use_cached_searches)

  # 2. Hit backends for any shards that are still needed.  When these results
  # come back, they are also put into unfiltered_iids_dict..
  for shard_id in needed_shard_ids:
    rpc = _StartBackendSearchCall(
        mr, query_project_names, shard_id,
        services.cache_manager.processed_invalidations_up_to)
    rpc_tuple = (time.time(), shard_id, rpc)
    rpc.callback = _MakeBackendCallback(
        _HandleBackendSearchResponse, mr, query_project_names, rpc_tuple,
        rpc_tuples, settings.backend_retries, unfiltered_iids_dict,
        search_limit_reached_dict,
        services.cache_manager.processed_invalidations_up_to,
        error_responses)
    rpc_tuples.append(rpc_tuple)

  return rpc_tuples


def _FinishBackendSearch(rpc_tuples):
  """Wait for all backend calls to complete, including any retries."""
  while rpc_tuples:
    active_rpcs = [rpc for (_time, _shard_id, rpc) in rpc_tuples]
    # Wait for any active RPC to complete.  It's callback function will
    # automatically be called.
    finished_rpc = apiproxy_stub_map.UserRPC.wait_any(active_rpcs)
    # Figure out which rpc_tuple finished and remove it from our list.
    for rpc_tuple in rpc_tuples:
      _time, _shard_id, rpc = rpc_tuple
      if rpc == finished_rpc:
        rpc_tuples.remove(rpc_tuple)
        break
    else:
      raise ValueError('We somehow finished an RPC that is not in rpc_tuples')


def _GetProjectTimestamps(query_project_ids, needed_shard_ids):
  """Get a dict of modified_ts values for all specified project-shards."""
  project_shard_timestamps = {}
  if query_project_ids:
    keys = []
    for pid in query_project_ids:
      for sid in needed_shard_ids:
        keys.append('%d;%d' % (pid, sid))
  else:
    keys = [('all;%d' % sid) for sid in needed_shard_ids]

  timestamps_for_project = memcache.get_multi(keys=keys)
  for key, timestamp in timestamps_for_project.iteritems():
    pid_str, sid_str = key.split(';')
    if pid_str == 'all':
      project_shard_timestamps['all', int(sid_str)] = timestamp
    else:
      project_shard_timestamps[int(pid_str), int(sid_str)] = timestamp

  return project_shard_timestamps


def _GetNonviewableIIDs(
    query_project_ids, logged_in_user_id, needed_shard_ids, rpc_tuples,
    nonviewable_iids, project_shard_timestamps, invalidation_timestep,
    use_cached_searches):
  """Build a set of at-risk IIDs, and accumulate RPCs to get uncached ones."""
  if query_project_ids:
    keys = []
    for pid in query_project_ids:
      for sid in needed_shard_ids:
        keys.append('%d;%d;%d' % (pid, logged_in_user_id, sid))
  else:
    keys = [('all;%d;%d' % sid)
            for (logged_in_user_id, sid) in needed_shard_ids]

  if use_cached_searches:
    cached_dict = memcache.get_multi(keys, key_prefix='nonviewable:')
  else:
    cached_dict = {}

  for sid in needed_shard_ids:
    if query_project_ids:
      for pid in query_project_ids:
        _AccumulateNonviewableIIDs(
            pid, logged_in_user_id, sid, cached_dict, nonviewable_iids,
            project_shard_timestamps, rpc_tuples, invalidation_timestep)
    else:
      _AccumulateNonviewableIIDs(
          None, logged_in_user_id, sid, cached_dict, nonviewable_iids,
          project_shard_timestamps, rpc_tuples, invalidation_timestep)


def _AccumulateNonviewableIIDs(
    pid, logged_in_user_id, sid, cached_dict, nonviewable_iids,
    project_shard_timestamps, rpc_tuples, invalidation_timestep):
  """Use one of the retrieved cache entries or call a backend if needed."""
  if pid is None:
    key = 'all;%d;%d' % (logged_in_user_id, sid)
  else:
    key = '%d;%d;%d' % (pid, logged_in_user_id, sid)

  if key in cached_dict:
    issue_ids, cached_ts = cached_dict.get(key)
    modified_ts = project_shard_timestamps.get((pid, sid))
    if modified_ts is None or modified_ts > cached_ts:
      logging.info('nonviewable too stale on (project %r, shard %r)',
                   pid, sid)
    else:
      logging.info('adding %d nonviewable issue_ids', len(issue_ids))
      nonviewable_iids[sid] = set(issue_ids)

  if sid not in nonviewable_iids:
    logging.info('nonviewable for %r not found', key)
    logging.info('starting backend call for nonviewable iids %r', key)
    rpc = _StartBackendNonviewableCall(
      pid, logged_in_user_id, sid, invalidation_timestep)
    rpc_tuple = (time.time(), sid, rpc)
    rpc.callback = _MakeBackendCallback(
        _HandleBackendNonviewableResponse, pid, logged_in_user_id, sid,
        rpc_tuple, rpc_tuples, settings.backend_retries, nonviewable_iids,
        invalidation_timestep)
    rpc_tuples.append(rpc_tuple)


def _GetCachedSearchResults(
    mr, query_project_ids, needed_shard_ids, harmonized_config,
    project_shard_timestamps, services):
  """Return a dict of cached search results that are not already stale.

  If it were not for cross-project search, we would simply cache when we do a
  search and then invalidate when an issue is modified.  But, with
  cross-project search we don't know all the memcache entries that would
  need to be invalidated.  So, instead, we write the search result cache
  entries and then an initial modified_ts value for each project if it was
  not already there. And, when we update an issue we write a new
  modified_ts entry, which implicitly invalidate all search result
  cache entries that were written earlier because they are now stale.  When
  reading from the cache, we ignore any query project with modified_ts
  after its search result cache timestamp, because it is stale.

  Args:
    mr: common information parsed from the request.
    query_project_ids: list of project ID numbers for all projects being
        searched.
    needed_shard_ids: set of shard IDs that need to be checked.
    harmonized_config: ProjectIsueConfig with combined information for all
        projects involved in this search.
    project_shard_timestamps: a dict {(project_id, shard_id): timestamp, ...}
        that tells when each shard was last invalidated.
    services: connections to backends.

  Returns:
    Tuple consisting of:
      A dictionary {shard_id: [issue_id, ...], ...} of unfiltered search result
      issue IDs. Only shard_ids found in memcache will be in that dictionary.
      The result issue IDs must be permission checked before they can be
      considered to be part of the user's result set.
      A dictionary {shard_id: bool, ...}. The boolean is set to True if
      the search results limit of the shard is hit.
  """
  projects_str = ','.join(str(pid) for pid in sorted(query_project_ids))
  projects_str = projects_str or 'all'
  canned_query = savedqueries_helpers.SavedQueryIDToCond(
      mr.cnxn, services.features, mr.can)
  logging.info('canned query is %r', canned_query)
  canned_query = searchpipeline.ReplaceKeywordsWithUserID(
      mr.me_user_id, canned_query)
  user_query = searchpipeline.ReplaceKeywordsWithUserID(
      mr.me_user_id, mr.query)

  sd = sorting.ComputeSortDirectives(mr, harmonized_config)
  memcache_prefix = ';'.join([projects_str, canned_query, user_query,
                              ' '.join(sd), ''])
  cached_dict = memcache.get_multi(
      [str(sid) for sid in needed_shard_ids], key_prefix=memcache_prefix)
  search_limit_memcache_prefix = ';'.join(
      [projects_str, canned_query, user_query,
       ' '.join(sd), 'search_limit_reached', ''])
  cached_search_limit_reached_dict = memcache.get_multi(
      [str(sid) for sid in needed_shard_ids],
      key_prefix=search_limit_memcache_prefix)

  unfiltered_dict = {}
  search_limit_reached_dict = {}
  for shard_id in needed_shard_ids:
    if str(shard_id) not in cached_dict:
      logging.info('memcache miss on shard %r', shard_id)
      continue

    cached_iids, cached_ts = cached_dict[str(shard_id)]
    if cached_search_limit_reached_dict.get(str(shard_id)):
      search_limit_reached, _ = cached_search_limit_reached_dict[str(shard_id)]
    else:
      search_limit_reached = False

    stale = False
    if query_project_ids:
      for project_id in query_project_ids:
        modified_ts = project_shard_timestamps.get((project_id, shard_id))
        if modified_ts is None or modified_ts > cached_ts:
          stale = True
          logging.info('memcache too stale on shard %r because of %r',
                       shard_id, project_id)
          break
    else:
      modified_ts = project_shard_timestamps.get(('all', shard_id))
      if modified_ts is None or modified_ts > cached_ts:
        stale = True
        logging.info('memcache too stale on shard %r because of all',
                     shard_id)

    if not stale:
      logging.info('memcache hit on %r', shard_id)
      unfiltered_dict[shard_id] = cached_iids
      search_limit_reached_dict[shard_id] = search_limit_reached

  return unfiltered_dict, search_limit_reached_dict


def _MakeBackendRequestHeaders(failfast):
  headers = {
    # This is needed to allow frontends to talk to backends without going
    # through a login screen on googleplex.com.
    # http://wiki/Main/PrometheusInternal#Internal_Applications_and_APIs
    'X-URLFetch-Service-Id': 'GOOGLEPLEX',
    }
  if failfast:
    headers['X-AppEngine-FailFast'] = 'Yes'
  return headers


def _StartBackendSearchCall(
    mr, query_project_names, shard_id, invalidation_timestep,
    deadline=None, failfast=True):
  """Ask a backend to query one shard of the database."""
  backend_host = modules.get_hostname(module='besearch')
  url = 'http://%s%s' % (backend_host, framework_helpers.FormatURL(
      mr, urls.BACKEND_SEARCH,
      projects=','.join(query_project_names),
      q=mr.query, start=0, num=mr.start + mr.num,
      logged_in_user_id=mr.auth.user_id or 0,
      me_user_id=mr.me_user_id, shard_id=shard_id,
      invalidation_timestep=invalidation_timestep))
  logging.info('\n\nCalling backend: %s', url)
  rpc = urlfetch.create_rpc(
      deadline=deadline or settings.backend_deadline)
  headers = _MakeBackendRequestHeaders(failfast)
  # follow_redirects=False is needed to avoid a login screen on googleplex.
  urlfetch.make_fetch_call(rpc, url, follow_redirects=False, headers=headers)
  return rpc


def _StartBackendNonviewableCall(
    project_id, logged_in_user_id, shard_id, invalidation_timestep,
    deadline=None, failfast=True):
  """Ask a backend to query one shard of the database."""
  backend_host = modules.get_hostname(module='besearch')
  url = 'http://%s%s' % (backend_host, framework_helpers.FormatURL(
      None, urls.BACKEND_NONVIEWABLE,
      project_id=project_id or '',
      logged_in_user_id=logged_in_user_id or '',
      shard_id=shard_id,
      invalidation_timestep=invalidation_timestep))
  logging.info('Calling backend nonviewable: %s', url)
  rpc = urlfetch.create_rpc(deadline=deadline or settings.backend_deadline)
  headers = _MakeBackendRequestHeaders(failfast)
  # follow_redirects=False is needed to avoid a login screen on googleplex.
  urlfetch.make_fetch_call(rpc, url, follow_redirects=False, headers=headers)
  return rpc


def _HandleBackendSearchResponse(
    mr, query_project_names, rpc_tuple, rpc_tuples, remaining_retries,
    unfiltered_iids, search_limit_reached, invalidation_timestep,
    error_responses):
  """Process one backend response and retry if there was an error."""
  start_time, shard_id, rpc = rpc_tuple
  duration_sec = time.time() - start_time

  try:
    response = rpc.get_result()
    logging.info('call to backend took %d sec', duration_sec)
    # Note that response.content has "})]'\n" prepended to it.
    json_content = response.content[5:]
    logging.info('got json text: %r length %r',
                 json_content[:framework_constants.LOGGING_MAX_LENGTH],
                 len(json_content))
    json_data = json.loads(json_content)
    unfiltered_iids[shard_id] = json_data['unfiltered_iids']
    search_limit_reached[shard_id] = json_data['search_limit_reached']

  except Exception as e:
    if duration_sec > FAIL_FAST_LIMIT_SEC:  # Don't log fail-fast exceptions.
      logging.exception(e)
    if not remaining_retries:
      logging.error('backend search retries exceeded')
      error_responses.add(shard_id)
      return  # Used all retries, so give up.

    if duration_sec >= settings.backend_deadline:
      logging.error('backend search on %r took too long', shard_id)
      error_responses.add(shard_id)
      return  # That backend shard is overloaded, so give up.

    logging.error('backend call for shard %r failed, retrying', shard_id)
    retry_rpc = _StartBackendSearchCall(
        mr, query_project_names, shard_id, invalidation_timestep,
        failfast=remaining_retries > 2)
    retry_rpc_tuple = (time.time(), shard_id, retry_rpc)
    retry_rpc.callback = _MakeBackendCallback(
        _HandleBackendSearchResponse, mr, query_project_names,
        retry_rpc_tuple, rpc_tuples, remaining_retries - 1, unfiltered_iids,
        search_limit_reached, invalidation_timestep, error_responses)
    rpc_tuples.append(retry_rpc_tuple)


def _HandleBackendNonviewableResponse(
    project_id, logged_in_user_id, shard_id, rpc_tuple, rpc_tuples,
    remaining_retries, nonviewable_iids, invalidation_timestep):
  """Process one backend response and retry if there was an error."""
  start_time, shard_id, rpc = rpc_tuple
  duration_sec = time.time() - start_time

  try:
    response = rpc.get_result()
    logging.info('call to backend nonviewable took %d sec', duration_sec)
    # Note that response.content has "})]'\n" prepended to it.
    json_content = response.content[5:]
    logging.info('got json text: %r length %r',
                 json_content[:framework_constants.LOGGING_MAX_LENGTH],
                 len(json_content))
    json_data = json.loads(json_content)
    nonviewable_iids[shard_id] = set(json_data['nonviewable'])

  except Exception as e:
    if duration_sec > FAIL_FAST_LIMIT_SEC:  # Don't log fail-fast exceptions.
      logging.exception(e)

    if not remaining_retries:
      logging.warn('Used all retries, so give up on shard %r', shard_id)
      return

    if duration_sec >= settings.backend_deadline:
      logging.error('nonviewable call on %r took too long', shard_id)
      return  # That backend shard is overloaded, so give up.

    logging.error(
      'backend nonviewable call for shard %r;%r;%r failed, retrying',
      project_id, logged_in_user_id, shard_id)
    retry_rpc = _StartBackendNonviewableCall(
        project_id, logged_in_user_id, shard_id, invalidation_timestep,
        failfast=remaining_retries > 2)
    retry_rpc_tuple = (time.time(), shard_id, retry_rpc)
    retry_rpc.callback = _MakeBackendCallback(
        _HandleBackendNonviewableResponse, project_id, logged_in_user_id,
        shard_id, retry_rpc_tuple, rpc_tuples, remaining_retries - 1,
        nonviewable_iids, invalidation_timestep)
    rpc_tuples.append(retry_rpc_tuple)


def _TotalLength(sharded_iids):
  """Return the total length of all issue_iids lists."""
  return sum(len(issue_iids) for issue_iids in sharded_iids.itervalues())


def _ReverseShards(sharded_iids):
  """Reverse each issue_iids list in place."""
  for shard_id in sharded_iids:
    sharded_iids[shard_id].reverse()


def _TrimEndShardedIIDs(sharded_iids, sample_iids, num_needed):
  """Trim the IIDs to keep at least num_needed items.

  Args:
    sharded_iids: dict {shard_id: issue_id_list} for search results.  This is
        modified in place to remove some trailing issue IDs.
    sample_iids: list of IIDs from a sorted list of sample issues.
    num_needed: int minimum total number of items to keep.  Some IIDs that are
        known to belong in positions > num_needed will be trimmed off.

  Returns:
    The total number of IIDs removed from the IID lists.
  """
  # 1. Get (sample_iid, position_in_shard) for each sample.
  sample_positions = _CalcSamplePositions(sharded_iids, sample_iids)

  # 2. Walk through the samples, computing a combined lower bound at each
  # step until we know that we have passed at least num_needed IIDs.
  lower_bound_per_shard = {}
  excess_samples = []
  for i in range(len(sample_positions)):
    sample_iid, pos = sample_positions[i]
    shard_id = sample_iid % settings.num_logical_shards
    lower_bound_per_shard[shard_id] = pos
    overall_lower_bound = sum(lower_bound_per_shard.itervalues())
    if overall_lower_bound >= num_needed:
      excess_samples = sample_positions[i + 1:]
      break
  else:
    return 0  # We went through all samples and never reached num_needed.

  # 3. Truncate each shard at the first excess sample in that shard.
  already_trimmed = set()
  num_trimmed = 0
  for sample_iid, pos in excess_samples:
    shard_id = sample_iid % settings.num_logical_shards
    if shard_id not in already_trimmed:
      num_trimmed += len(sharded_iids[shard_id]) - pos
      sharded_iids[shard_id] = sharded_iids[shard_id][:pos]
      already_trimmed.add(shard_id)

  return num_trimmed


# TODO(jrobbins): Convert this to a python generator.
def _CalcSamplePositions(sharded_iids, sample_iids):
  """Return [(sample_iid, position_in_shard), ...] for each sample."""
  # We keep track of how far index() has scanned in each shard to avoid
  # starting over at position 0 when looking for the next sample in
  # the same shard.
  scan_positions = collections.defaultdict(lambda: 0)
  sample_positions = []
  for sample_iid in sample_iids:
    shard_id = sample_iid % settings.num_logical_shards
    try:
      pos = sharded_iids.get(shard_id, []).index(
          sample_iid, scan_positions[shard_id])
      scan_positions[shard_id] = pos
      sample_positions.append((sample_iid, pos))
    except ValueError:
      pass

  return sample_positions


def _SortIssues(mr, issues, config, users_by_id):
  """Sort the found issues based on the request and config values.

  Args:
    mr: common information parsed from the HTTP request.
    issues: A list of issues to be sorted.
    config: A ProjectIssueConfig that could impact sort order.
    users_by_id: dictionary {user_id: user_view,...} for all users who
      participate in any issue in the entire list.

  Returns:
    A sorted list of issues, based on parameters from mr and config.
  """
  issues = sorting.SortArtifacts(
      mr, issues, config, tracker_helpers.SORTABLE_FIELDS,
      username_cols=tracker_constants.USERNAME_COLS, users_by_id=users_by_id)
  return issues
