# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Search index functions.

 * find() function searches for docs.
 * Crawls for documents in repos of registered projects, incrementally updates
   the index.

See also README.md
"""

import datetime
import json
import logging
import posixpath
import re
import traceback
import urlparse

from google.appengine.api import app_identity
from google.appengine.api import search
from google.appengine.ext import db
from google.appengine.ext import deferred
from google.appengine.ext import ndb

from components import config
from components import gitiles
from components import net
from components import utils


# Coarse ACL:
PUBLIC_HOSTNAMES = ['chromium.googlesource.com']

REF_ID_RGX = re.compile('^([^/]+)/([^+]+?)/\+/(.+)$')


################################################################################
# Search index contains .md files rendered to HTML.

# Ids of documents in this index are URLs to the documents without a scheme,
# e.g. "chromium.googlesource.com/infra/infra/+/HEAD/doc/index.md"

INDEX = search.Index(name='documentation')

FIELD_TITLE = 'title'  # Inner text of <title> tag.
FIELD_CONTENT = 'content'  # Rendered HTML of a markdown file.

FACET_HOSTNAME = 'hostname'  # e.g. chromium.googlesource.com
FACET_PROJECT = 'project'  # e.g. infra/infra
FACET_REF = 'ref'  # always 'refs/heads/master'


################################################################################
# Search


def find(query_string, include_internal=False):
  """Searches for documents with a content snippet.

  Args:
    query_string (str): see appengine docs for query_string format.
      In short, it is a words that should appear in the document.
    include_internal (bool): True to include docs in internal repos.
      Defaults to False.

  Returns:
    An iterable of dicts, each dict has keys:
      * url: url to the document.
      * title: document title
      * snippet: matching content snippet.
  """
  options = search.QueryOptions(
      returned_fields=[FIELD_TITLE],
      snippeted_fields=[FIELD_CONTENT],
      limit=100,
      # Sort by score.
      sort_options=search.SortOptions(
          match_scorer=search.MatchScorer(),
          expressions=[
            search.SortExpression(
                expression='_score',
                # Non-intuitively, DESCENDING is what we needed here.
                direction=search.SortExpression.DESCENDING,
                default_value=0.0)
          ],
      ),
  )
  return_facets=[search.FacetRequest(FACET_HOSTNAME, values=PUBLIC_HOSTNAMES)]
  if include_internal:
    return_facets = []
  query = search.Query(
      query_string=query_string,
      options=options,
      return_facets=return_facets)
  result = INDEX.search(query)

  to_dict = lambda pairs: {p.name: p.value for p in pairs}
  for doc in result.results:
    fields = to_dict(doc.fields)
    expr = to_dict(doc.expressions)
    yield {
      'url': 'https://%s' % doc.doc_id,
      'title': fields[FIELD_TITLE],
      'snippet': expr['content'],
    }


################################################################################
# Crawling: cron job.


class Ref(ndb.Model):
  """Stores last imported revision of a gitiles location and indexing state.

  Entity key:
    Root entity. ID is "<hostname>/<project>/+/<ref>".
  """
  # Revision known to be indexed. If None, index state is undefined.
  indexed_revision = ndb.StringProperty()
  # Target revision of indexing. If different from indexed_revision, then
  # the indexing is in the process. If indexing_revision is None, all documents
  # must be deleted. If both indexing_revision and indexed_revision are None,
  # index state is undefined and indexing is not in the process.
  indexing_revision = ndb.StringProperty(indexed=False)
  last_added_dir = ndb.StringProperty(indexed=False)
  indexing_started_ts = ndb.DateTimeProperty(indexed=False)


def cron_crawl():
  ref_ids = set()
  for loc in get_locations_to_index():
    ref_id = loc_to_ref_id(loc)
    ref_ids.add(ref_id)
    try:
      try_update(ref_id)
    except net.AuthError as ex:  # pragma: no coverage
      logging.error('AuthError during crawling %s: %s', ref_id, ex.message)

  all_refs = Ref.query().fetch()
  for ref in all_refs:
    if ref.key.id() not in ref_ids:
      try_update(ref.key.id(), delete=True)

  now = utils.utcnow()
  for ref in all_refs:
    if ref.indexing_revision != ref.indexed_revision:
      if now - ref.indexing_started_ts > datetime.timedelta(hours=3):
        logging.error(
            'Indexing of %s did not complete in 3 hours', ref.key.id())


def get_locations_to_index():
  """Returns registered gitiles projects."""
  for project in config.get_projects():
    if project.repo_type != 'GITILES':
      continue
    try:
      loc = gitiles.Location.parse(project.repo_url)
    except ValueError:
      logging.exception(
          'Could not parse project %s repo url: %s',
          project.id, project.repo_url)
    else:
      yield loc._replace(treeish='HEAD', path='/')


################################################################################
# Crawling: guts.


@ndb.transactional
def try_update(ref_id, delete=False):
  """Starts updating all documents given a ref_id.

  Does nothing if indexing is in the process. Otherwise, transactionally
  updates Ref.indexing_revision and enqueues a push task to update all documents
  with |ref_id|.
  """
  ref = Ref.get_by_id(ref_id)
  ref_exists = bool(ref)
  ref = ref or Ref(id=ref_id)

  if ref.indexing_revision != ref.indexed_revision:
    logging.debug(
        'Indexing of %s is in the process: %r -> %r',
        ref_id, ref.indexed_revision, ref.indexing_revision)
    return

  latest = None
  if not delete:
    log = ref_id_to_loc(ref_id).get_log(limit=1)
    if log:
      latest = log.commits[0]
  if latest:
    if ref.indexed_revision == latest.sha:
      return
  elif not ref_exists:
    return
  ref.indexing_revision = latest.sha if latest else None  # None for deletion
  ref.indexing_started_ts = utils.utcnow()
  ref.last_added_dir = None
  ref.put()
  deferred.defer(_task_update, ref_id, _transactional=True)


def _task_update(ref_id):
  """Updates documents within a ref. Idempotent."""
  hostname, project, ref_name = parse_ref_id(ref_id)
  loc = ref_id_to_loc(ref_id)

  ref = Ref.get_by_id(ref_id)
  from_commit = ref.indexed_revision if ref else None
  to_commit = ref.indexing_revision if ref else None

  logging.info('Updating %s: %r -> %r', ref_id, from_commit, to_commit)
  if from_commit == to_commit:
    if to_commit is not None:
      logging.info('Already indexed')
      return
    # Index state is undefined and documents are requested to be deleted.

  if from_commit and to_commit:
    diff = gitiles.get_diff(hostname, project, from_commit, to_commit, '/')
    if diff is None:
      # May happen if |from_commit| does not exist anymore (git push --force)
      logging.warning('Could not load diff %s..%s', from_commit, to_commit)
    else:
      deleted = set()
      added = set()
      deleted_prefix = '--- a/'
      added_prefix = '+++ b/'
      for line in diff.splitlines():
        if line.startswith(deleted_prefix) and line.lower().endswith('.md'):
          deleted.add(line[len(deleted_prefix):])
        elif line.startswith(added_prefix) and line.lower().endswith('.md'):
          added.add(line[len(added_prefix):])
      logging.debug('%d deleted: %r', len(deleted), list(sorted(deleted)))
      logging.debug('%d added: %r', len(added), list(sorted(added)))
      INDEX.delete(['%s/%s' % (ref_id, path) for path in deleted])
      added_locs = map(loc.join, added)
      INDEX.put(_load_docs_async(added_locs, to_commit).get_result())
      _mark_as_indexed(ref_id, from_commit, to_commit)
      return

  if to_commit:
    logging.warning('Doing a full refresh')
    _delete_all(hostname, project, ref_name)
    # Crawling an entire tree and adding all documents may not be performed in a
    # single run, so enqueue a task that will eventually add them all.
    deferred.defer(_task_add_all, ref_id, to_commit)
  else:
    logging.warning('Deleting all docs')
    _delete_all(hostname, project, ref_name)
    _mark_as_indexed(ref_id, from_commit, to_commit)


@ndb.transactional
def _mark_as_indexed(ref_id, from_commit, to_commit):
  ref = Ref.get_by_id(ref_id)
  if not ref:
    if to_commit is None:
      return
    else:  # pragma: no cover
      logging.error('Ref %s was deleted during indexing %s', ref_id, to_commit)
      ref = Ref(id=ref_id)
  elif (ref.indexed_revision != from_commit or
      ref.indexing_revision != to_commit):  # pragma: no cover
    # This should never happen.
    logging.error('Ref %s was changed during indexing', ref_id)
  if to_commit is None:
    ref.key.delete()
  else:
    ref.indexed_revision = to_commit
    ref.indexing_started_ts = None
    ref.put()
  logging.info('Updated %s to %s', ref_id, to_commit)


@ndb.tasklet
def _load_docs_async(locs, rev):
  """Loads rendered .md files from Gitiles as a list of search.Documents.

  Args:
    locs (list of gitiles.Location): locations of files to import.
    rev (str): revision of files to import.
  """
  fixed_locs = [l._replace(treeish=rev) for l in locs]
  headers = {
    'User-Agent': app_identity.get_default_version_hostname(),
  }
  htmls = yield [
    net.request_async(str(l), headers=headers)
    for l in fixed_locs
  ]
  raise ndb.Return([
    create(loc, html) for loc, html in zip(locs, htmls)
  ])


def create(loc, content):
  return search.Document(
      doc_id=loc_to_doc_id(loc),
      fields=[
        search.TextField(name=FIELD_TITLE, value=get_title(content)),
        search.HtmlField(name=FIELD_CONTENT, value=content),
      ],
      facets=[
        search.AtomFacet(name=FACET_HOSTNAME, value=loc.hostname),
        search.AtomFacet(name=FACET_PROJECT, value=loc.project),
        search.AtomFacet(name=FACET_REF, value=loc.treeish),
      ],
  )


def _delete_all(hostname, project, ref):
  """Deletes all documents imported from (hostname, project, ref)."""
  logging.warning('Deleting all from %s/%s/+/%s', hostname, project, ref)
  cursor = search.Cursor()
  while cursor:
    query = search.Query(
        query_string='',
        facet_refinements=[
          search.FacetRefinement(name=FACET_HOSTNAME, value=hostname),
          search.FacetRefinement(name=FACET_PROJECT, value=project),
          search.FacetRefinement(name=FACET_REF, value=ref),
        ],
        options=search.QueryOptions(ids_only=True, cursor=cursor))
    result = INDEX.search(query)
    if not result.results:
      break
    INDEX.delete([d.doc_id for d in result.results])
    cursor = result.cursor


def _task_add_all(ref_id, rev, _update_frequency=None):
  """Crawls entire ref tree and adds all .md files.

  During task execution, it saves the last imported dir in Ref.last_added_dir,
  so it can continue if it fails, and eventually will add all documents @ |rev|,
  even if it is temporarily out of Gitiles quota.

  Directory scanning is done in pre-order serially.

  Returns:
    Number of imported documents.
  """
  if _update_frequency is None:
    _update_frequency = datetime.timedelta(seconds=1)
  logging.info('Adding %s @ %s', ref_id, rev)
  root = ref_id_to_loc(ref_id)
  ref = Ref.get_by_id(ref_id)
  if not ref or ref.indexing_revision == ref.indexed_revision:
    # Nothing to do.
    return  # pragma: no cover
  if ref.indexing_revision != rev:
    logging.error(
        'Indexing revision changed to %s. Abort mission.',
        ref.indexing_revision)
    return
  # This ref is "locked". The fact that this task is executed means the task
  # has exclusive rights to the ref.

  # {path -> sorted list of gitiles.TreeEntry} map
  class Entries(dict):
    @utils.memcache('trees[%s, %s]' % (ref_id, rev), ['path'])
    def __missing__(self, path):
      tree = root._replace(treeish=rev, path=path).get_tree()
      if tree is None:
        # Tree is not found. Did the commit disappear?
        if gitiles.get_commit(root.hostname, root.project, rev) is None:
          logging.error('Commit %s disappeared')
          raise CancelTask()
        else:   # pragma: no coverage
          raise Exception('Tree is not found. Retry the task')
      return sorted(tree.entries, key=lambda e: e.name)
  entries = Entries()

  subdirs = lambda p: (e.name for e in entries[p] if e.type == 'tree')
  get_next = lambda path: pre_order_next(path, subdirs)

  def main():
    # Restore state.
    if ref.last_added_dir:
      cur_path = get_next(ref.last_added_dir)
      logging.info('Starting from %s', cur_path)
    else:
      cur_path = '/'

    last_update_time = utils.utcnow()

    # Pre-order tree travesal.
    while cur_path:
      md_file_locs = []
      for e in entries[cur_path]:
        if e.type == 'blob' and e.name.lower().endswith('.md'):
          md_full_name = posixpath.join(cur_path, e.name)
          md_file_locs.append(root._replace(path=md_full_name))

      if md_file_locs:
        INDEX.put(_load_docs_async(md_file_locs, rev).get_result())

      if utils.utcnow() - last_update_time >= _update_frequency:
        try:
          ref.last_added_dir = cur_path
          ref.put()
          last_update_time = utils.utcnow()
          logging.info('Processed %s', cur_path)
        except db.Error:  # pragma: no coverage
          # Best effort. If we failed to persist last added dir, this is fine.
          # We can probably save it next time.
          # Anyway, we have a 3 hrs timeout before alerts start to fire.
          logging.warning(
              'Could not save Ref.last_added_dir: %s', traceback.format_exc())

      cur_path = get_next(cur_path)

  @ndb.transactional
  def update_ref(new_rev):
    ref = Ref.get_by_id(ref_id)
    if not ref:  # pragma: no cover
      logging.error('Ref disappeared during _task_add_all execution')
      return
    if ref.indexing_revision != rev:  # pragma: no cover
      logging.error(
          'Indexing of %s has started while _task_add_all was indexing %s',
          ref.indexing_revision, rev)
      return
    ref.indexed_revision = new_rev
    ref.indexing_revision = new_rev
    ref.last_added_dir = None
    ref.indexing_started_ts = None
    ref.put()

  try:
    main()
    update_ref(rev)
  except CancelTask:
    # Suppress exception, so the task is not retried.
    # By setting indexed_revision to None, we force full-rescan next time.
    update_ref(None)


################################################################################
# Misc

class CancelTask(Exception):
  """If raised in _task_add_all, the task is not retried."""


def loc_to_doc_id(loc):
  """Converts a gitiles.Location to search.Document doc_id."""
  parsed = urlparse.urlparse(str(loc))
  return '%s%s' % (parsed.netloc, parsed.path)


def loc_to_ref_id(loc):
  return '{hostname}/{project}/+/{treeish}'.format(**loc._asdict())


def parse_ref_id(ref_id):
  """Returns (hostname, project, ref) from |ref_id|."""
  m = REF_ID_RGX.match(ref_id)
  # All ref_ids in this app depend on get_locations_to_index which
  # guarantees to return valid locations.
  assert m
  return m.groups()


def ref_id_to_loc(ref_id):
  hostname, project, ref = parse_ref_id(ref_id)
  return gitiles.Location(hostname, project, ref, '/')


def get_title(html):
  """Finds a title in a HTML document."""
  title_tag = '<title>'
  start = html.find(title_tag)
  if start < 0:
    return None
  end = html.find('</title>', start)
  if end < 0:
    return None
  return html[start + len(title_tag): end]


def pre_order_next(path, children):
  """Returns the next dir for pre-order traversal."""
  assert path.startswith('/'), path

  # First subdir is next
  for subdir in children(path):
    return posixpath.join(path, subdir)

  while path != '/':
    # Next sibling is next
    name = posixpath.basename(path)
    parent = posixpath.dirname(path)
    siblings = list(children(parent))
    assert name in siblings
    if name != siblings[-1]:
      return posixpath.join(parent, siblings[siblings.index(name) + 1])
    # Go up, find a sibling of the parent.
    path = parent

  # This was the last one
  return None
