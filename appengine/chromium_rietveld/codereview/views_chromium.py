# Copyright 2008 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Views for Chromium port of Rietveld."""

import datetime
import logging
import random
import re

from google.appengine.datastore import datastore_query

from django.http import HttpResponse

from codereview import decorators as deco
from codereview import decorators_chromium as deco_cr
from codereview import models


### Utility functions ###


def _is_job_valid(job):
  """Determines if a pending try job result is valid or not.

  Pending try job results are those with result is set to
  models.TryJobResult.TRYPENDING.  These jobs are invalid if:

  - their associated issue is already committed, or
  - their associated issue is marked private, or
  - their associated PatchSet is no longer the latest in the issue.

  Args:
    job: an instance of models.TryJobResult.

  Returns:
    True if the pending try job is invalid, False otherwise.
  """
  if job.result == models.TryJobResult.TRYPENDING:
    patchset_key = job.key.parent()
    issue_key = patchset_key.parent()
    issue_future = issue_key.get_async()
    last_patchset_key_future = models.PatchSet.query(ancestor=issue_key).order(
      -models.PatchSet.created).get_async(keys_only=True)

    issue = issue_future.get_result()
    if issue.closed or issue.private:
      return False

    last_patchset_key = last_patchset_key_future.get_result()
    if last_patchset_key != patchset_key:
      return False

  return True


### View handlers ###

@deco_cr.binary_required
def download_binary(request):
  """/<issue>/binary/<patchset>/<patch>/<content>

  Return patch's binary content.  If the patch is not binary, an empty stream
  is returned.  <content> may be 0 for the base content or 1 for the new
  content.  All other values are invalid.
  """
  response = HttpResponse(request.content.data, content_type=request.mime_type)
  filename = re.sub(
      r'[^\w\.]', '_', request.patch.filename.encode('ascii', 'replace'))
  response['Content-Disposition'] = 'attachment; filename="%s"' % filename
  return response


@deco.json_response
@deco.require_methods('GET')
def get_pending_try_patchsets(request):
  limit = int(request.GET.get('limit', '10'))
  if limit > 1000:
    limit = 1000

  master = request.GET.get('master', None)
  encoded_cursor = request.GET.get('cursor', None)
  cursor = None
  if encoded_cursor:
    cursor = datastore_query.Cursor(urlsafe=encoded_cursor)

  def MakeJobDescription(job):
    patchset_future = job.key.parent().get_async()
    issue_future = job.key.parent().parent().get_async()
    patchset = patchset_future.get_result()
    issue = issue_future.get_result()
    owner = issue.owner

    # The job description is the basically the job itself with some extra
    # data from the patchset and issue.
    description = job.to_dict()
    description['name'] = '%d-%d: %s' % (issue.key.id(), patchset.key.id(),
                                         patchset.message)
    description['user'] = owner.nickname()
    description['email'] = owner.email()
    if ('chromium/blink' in issue.base
        or (issue.base.startswith('svn:')
            and issue.base.endswith('blink/trunk'))):
      description['root'] = 'src/third_party/WebKit'
    elif ('native_client/src/native_client' in issue.base
        or (issue.base.startswith('svn:')
            and issue.base.endswith('native_client/trunk/src/native_client'))):
      description['root'] = 'native_client'
    elif ('external/gyp' in issue.base
        or (issue.base.startswith('http://gyp.')
            and issue.base.endswith('svn/trunk'))
        or (issue.base.startswith('https://gyp.')
            and issue.base.endswith('svn/trunk'))):
      description['root'] = 'trunk'
    else:
      description['root'] = 'src'
    description['patch_project'] = issue.project
    description['patchset'] = patchset.key.id()
    description['issue'] = issue.key.id()
    description['baseurl'] = issue.base
    return description

  # This uses eventual consistency and cannot be made strongly consistent.
  q = models.TryJobResult.query(
      models.TryJobResult.result == models.TryJobResult.TRYPENDING)
  if master:
    q = q.filter(models.TryJobResult.master == master)
  q = q.order(models.TryJobResult.timestamp)

  # We do not simply use fetch_page() because we do some post-filtering which
  # could lead to under-filled pages.   Instead, we iterate, filter and keep
  # going until we have enough post-filtered results, then return those along
  # with the cursor after the last item.
  jobs = []  # List of dicts to return as JSON. One dict for each TryJobResult.
  total = 0
  next_cursor = None
  query_iter = q.iter(start_cursor=cursor, produce_cursors=True)
  for job in query_iter:
    total += 1
    if _is_job_valid(job):
      jobs.append(MakeJobDescription(job))
      if len(jobs) >= limit:
        break

  # If we stopped because we hit the limit, then there are probably more to
  # get with next_cursor.  This could be wrong in the case where all
  # TryJobResults with later timestamps are not valid, but that is rare and
  # it is harmless for the client to request the next page and get zero results.
  has_more = (len(jobs) >= limit)

  # If any jobs are returned, also include a cursor to try to get more.
  # If no jobs, keep the same cursor to allow 'tail -f' behavior.
  if jobs:
    next_cursor = query_iter.cursor_after()
  else:
    next_cursor = cursor

  logging.info('Found %d entries, returned %d' % (total, len(jobs)))
  return {
    'has_more': has_more,
    'cursor': next_cursor.urlsafe() if next_cursor else '',
    'jobs': jobs
    }
