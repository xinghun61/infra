# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections
import contextlib
import datetime
import json
import os

from google.appengine.api import search
from google.appengine.ext import deferred
from google.appengine.ext import ndb

from components import config
from components import gitiles
from components import net
from components import utils
from testing_utils import testing
import mock

import docs


INFRA_REF_ID = 'chromium.googlesource.com/infra/infra/+/HEAD'
INFRA_LOC = docs.ref_id_to_loc(INFRA_REF_ID)
DOC_DIR_LOC = INFRA_LOC.join('doc')


class DocsTest(testing.AppengineTestCase):

  def setUp(self):
    super(DocsTest, self).setUp()
    self.mock(deferred, 'defer', mock.Mock())
    self.mock(gitiles, 'get_log', mock.Mock())

  def mock_ref(self, indexed=True):
    ref = docs.Ref(
      id=INFRA_REF_ID,
      indexing_revision='deadbeef',
      indexed_revision='deadbeef' if indexed else None,
      indexing_started_ts=utils.utcnow(),
    )
    ref.put()

  def mock_tree(self):
    self.mock(gitiles, 'get_tree_async', mock.Mock())

    # pylint: disable=unused-argument
    @ndb.tasklet
    def get_tree(hostname, project, treeish, path):
      if path == '/':
        tree = gitiles.Tree(
          id='deadbeef',
          entries=[
            gitiles.TreeEntry(
              id='abc',
              name='foo',
              type='tree',
              mode=None,
            ),
            gitiles.TreeEntry(
              id='abcc',
              name='bar',
              type='tree',
              mode=None,
            ),
            gitiles.TreeEntry(
              id='abc',
              name='a.md',
              type='blob',
              mode=None,
            ),
            gitiles.TreeEntry(
              id='abc',
              name='b.md',
              type='blob',
              mode=None,
            ),
            gitiles.TreeEntry(
              id='abc',
              name='PRESUBMIT.py',
              type='blob',
              mode=None,
            ),
          ],
        )
      elif path == '/foo':
        tree = gitiles.Tree(
          id='deadbeef2',
          entries=[
            gitiles.TreeEntry(
              id='abc',
              name='c.md',
              type='blob',
              mode=None,
            ),
          ]
        )
      else:
        tree = gitiles.Tree(id='empty', entries=[])
      raise ndb.Return(tree)

    gitiles.get_tree_async.side_effect = get_tree

  def mock_html_contents(self):
    self.mock(net, 'request_async', mock.Mock())

    @ndb.tasklet
    def request_async(url, headers):  # pylint: disable=unused-argument
      name = os.path.basename(url)
      raise ndb.Return(html('Title of %s' % name, 'Contents of %s' % name))

    net.request_async.side_effect = request_async

  def mock_projects(self, empty=False):
    self.mock(config, 'get_projects', mock.Mock())
    if empty:
      config.get_projects.return_value = []
    else:
      config.get_projects.return_value = [
        config.Project(
            id='infra',
            name='Chromium infrastructure',
            repo_type='GITILES',
            repo_url='https://chromium.googlesource.com/infra/infra',
        ),
        config.Project(
            id='wrongurl',
            name=None,
            repo_type='GITILES',
            repo_url='wrongurl',
        ),
        config.Project(
            id='nongitiles',
            name=None,
            repo_type='GITHUB',
            repo_url='http://github.com/foo/bar',
        ),
      ]

  def test_find(self):
    docs.INDEX.put([
      docs.create(DOC_DIR_LOC.join('index.md'), html('Docs', 'Documentation!')),
      docs.create(DOC_DIR_LOC.join('foo'), html('Foo', 'Foooo')),
      docs.create(DOC_DIR_LOC.join('bar'), html('Bar', 'Barrr')),
    ])
    results = list(docs.find('foo'))
    self.assertEqual(results, [
      {
        'url': str(DOC_DIR_LOC.join('foo')),
        'title': 'Foo',
        'snippet': (
            # Snippets are broken on dev server
            '...<b><html</b> <head <title Foo< title < head '
            '<body Foooo< body < html...'),
      }
    ])

  def test_try_delete_idempotent(self):
    self.mock_ref()
    docs.try_update(INFRA_REF_ID, delete=True)
    self.assertTrue(deferred.defer.called)
    deferred.defer.reset_mock()

    docs.Ref(id=INFRA_REF_ID).key.delete()  # Mark as deleted.
    docs.try_update(INFRA_REF_ID, delete=True)
    self.assertFalse(deferred.defer.called)

  def test_cron_crawl(self):
    self.mock_projects()

    gitiles.get_log.return_value = gitiles.Log(
        commits=[gitiles.Commit(
            sha='deadbeef',
            tree='abc',
            parents=[],
            author=None,
            committer=None,
            message='Hi',
            tree_diff=[]
        )],
        next_cursor=None,
    )

    docs.cron_crawl()

    gitiles.get_log.assert_called_once_with(
        INFRA_LOC.hostname, INFRA_LOC.project, INFRA_LOC.treeish, '/', limit=1)
    cr_ref = docs.Ref.get_by_id(INFRA_REF_ID)
    self.assertIsNotNone(cr_ref)
    self.assertEqual(cr_ref.indexing_revision, 'deadbeef')
    self.assertEqual(cr_ref.indexed_revision, None)
    deferred.defer.assert_called_once_with(
        docs._task_update,
        INFRA_REF_ID,
        _transactional=True)

    # Calling cron_crawl again should be a noop
    # because indexing is in the process
    deferred.defer.reset_mock()
    docs.cron_crawl()  # Must be a noop.
    self.assertFalse(deferred.defer.called)

    # Now pretend it was indexed
    cr_ref.indexed_revision = cr_ref.indexing_revision
    cr_ref.put()
    # Calling cron_crawl again should be a noop
    # because there were no changes
    deferred.defer.reset_mock()
    docs.cron_crawl()  # Must be a noop.
    self.assertFalse(deferred.defer.called)

  def test_cron_crawl_delete_project_removed(self):
    self.mock_ref()
    self.mock_projects(empty=True)

    docs.cron_crawl()

    ref = docs.Ref.get_by_id(INFRA_REF_ID)
    self.assertIsNotNone(ref)
    self.assertEqual(None, ref.indexing_revision)  # Marked for deletion.

    deferred.defer.assert_called_once_with(
        docs._task_update,
        INFRA_REF_ID,
        _transactional=True)

  def test_task_update_delete_absent_ref(self):
    docs._task_update(INFRA_REF_ID)

  def test_cron_crawl_delete_no_log(self):
    self.mock_ref()
    self.mock_projects()
    gitiles.get_log.return_value = None

    docs.cron_crawl()

    ref = docs.Ref.get_by_id(INFRA_REF_ID)
    self.assertIsNotNone(ref)
    self.assertEqual(None, ref.indexing_revision)  # Marked for deletion.

    deferred.defer.assert_called_once_with(
        docs._task_update,
        INFRA_REF_ID,
        _transactional=True)

  def test_cron_crawl_indexing_took_too_long(self):
    ref = docs.Ref(
        id=INFRA_REF_ID,
        indexing_revision='deadbeef',
        indexing_started_ts=datetime.datetime(2000, 1, 1))
    ref.put()

    docs.cron_crawl()

    # If the alerting code is not execute, coverage will be < 100% which
    # is considered a failure

  def test_task_add_all(self):
    self.mock_tree()
    self.mock_html_contents()
    ref = docs.Ref(
        id=INFRA_REF_ID,
        indexing_revision='deadbeef',
    )
    ref.put()

    docs._task_add_all(
        INFRA_REF_ID, 'deadbeef', _update_frequency=datetime.timedelta(0))

    results = docs.find('Contents', include_internal=True)  # Find all.
    urls = sorted(r['url'] for r in results)
    self.assertEqual(urls, [
      'https://chromium.googlesource.com/infra/infra/+/HEAD/a.md',
      'https://chromium.googlesource.com/infra/infra/+/HEAD/b.md',
      'https://chromium.googlesource.com/infra/infra/+/HEAD/foo/c.md',
    ])

    ref = docs.Ref.get_by_id(INFRA_REF_ID)
    self.assertEqual(ref.indexing_revision, ref.indexed_revision)
    # Assert the task cleaned up after itself
    self.assertIsNone(ref.last_added_dir)
    self.assertIsNone(ref.indexing_started_ts)

  def test_task_add_all_continuation(self):
    self.mock_tree()
    self.mock_html_contents()
    self.mock_ref(False)
    ref = docs.Ref(
        id=INFRA_REF_ID,
        indexing_revision='deadbeef',
        last_added_dir='/',
    )
    ref.put()

    docs._task_add_all(INFRA_REF_ID, 'deadbeef')

    results = docs.find('Contents', include_internal=True)  # Find all.
    urls = sorted(r['url'] for r in results)
    # Files in the root are not added.
    self.assertEqual(urls, [
      'https://chromium.googlesource.com/infra/infra/+/HEAD/foo/c.md',
    ])

    ref = docs.Ref.get_by_id(INFRA_REF_ID)
    self.assertEqual(ref.indexing_revision, ref.indexed_revision)
    # Assert the task cleaned up after itself
    self.assertIsNone(ref.last_added_dir)
    self.assertIsNone(ref.indexing_started_ts)

  def test_task_add_all_unexpected_indexing_revision(self):
    self.mock_ref(False)
    self.mock_tree()
    docs._task_add_all(INFRA_REF_ID, 'different-rev')
    self.assertFalse(gitiles.get_tree_async.called)

  def test_task_add_all_commit_removed(self):
    self.mock_ref(indexed=False)

    self.mock(gitiles, 'get_tree_async', mock.Mock())
    gitiles.get_tree_async.return_value = ndb.Future()
    gitiles.get_tree_async.return_value.set_result(None)

    self.mock(gitiles, 'get_commit', mock.Mock())
    gitiles.get_commit.return_value = None

    docs._task_add_all(INFRA_REF_ID, 'deadbeef')

    ref = docs.Ref.get_by_id(INFRA_REF_ID)
    self.assertIsNone(ref.indexing_revision)

  def test_task_update_idempotent(self):
    self.mock_ref()
    self.mock(docs, 'INDEX', mock.Mock())
    docs._task_update(INFRA_REF_ID)
    self.assertFalse(docs.INDEX.put.called)
    self.assertFalse(docs.INDEX.delete.called)

  def test_task_update_full_refresh(self):
    self.mock_ref(indexed=False)

    docs.INDEX.put([
      docs.create(
          DOC_DIR_LOC.join('%d.md' % i),
          html('Title %d' % i, 'Contents %d' % i),
      )
      for i in xrange(20)
    ])
    results = list(docs.find('Contents', include_internal=True))  # Find all.
    self.assertEqual(20, len(results))

    docs._task_update(INFRA_REF_ID)

    results = list(docs.find('Contents', include_internal=True))  # Find all.
    self.assertEqual(0, len(results))
    # Assert adding all was scheduled
    deferred.defer.assert_called_once_with(
        docs._task_add_all, INFRA_REF_ID, 'deadbeef')

  def test_task_update_delete(self):
    ref = docs.Ref(
        id=INFRA_REF_ID, indexed_revision='deadbeef', indexing_revision=None)
    ref.put()

    docs.INDEX.put([
      docs.create(
          DOC_DIR_LOC.join('%d.md' % i),
          html('Title %d' % i, 'Contents %d' % i),
      )
      for i in xrange(20)
    ])

    docs._task_update(INFRA_REF_ID)

    results = list(docs.find('Contents', include_internal=True))  # Find all.
    self.assertEqual(0, len(results))
    self.assertIsNone(docs.Ref.get_by_id(INFRA_REF_ID))

  def test_full_no_diff(self):
    self.mock_ref(indexed=False)
    ref = docs.Ref(
        id=INFRA_REF_ID, indexed_revision='aaa', indexing_revision='bbb')
    ref.put()

    # Could not load a patch.
    self.mock(gitiles, 'get_diff', mock.Mock(return_value=None))

    docs._task_update(INFRA_REF_ID)

    # Assert adding all was scheduled
    deferred.defer.assert_called_once_with(
        docs._task_add_all, INFRA_REF_ID, 'bbb')

  def test_incremental_update(self):
    self.mock_html_contents()
    ref = docs.Ref(
        id=INFRA_REF_ID, indexed_revision='abc', indexing_revision='def')
    ref.put()

    self.mock(gitiles, 'get_diff', mock.Mock())
    gitiles.get_diff.return_value = '\n'.join([
      # Modified
      '--- a/modified.md',
      '+++ b/modified.md',
      'the difference',

      # Deleted
      '--- a/deleted.md',
      '+++ /dev/null', # deleted

      # Added
      '--- /dev/null',
      '+++ b/added.md', # deleted
    ])

    self.mock(docs, 'INDEX', mock.Mock())

    docs._task_update(INFRA_REF_ID)

    deleted_doc_ids = docs.INDEX.delete.call_args[0][0]
    self.assertEqual(
        set(deleted_doc_ids),
        {
          '%s/modified.md' % INFRA_REF_ID,
          '%s/deleted.md' % INFRA_REF_ID,
        }
    )

    added_docs = sorted(docs.INDEX.put.call_args[0][0], key=lambda d: d.doc_id)
    self.assertEqual(added_docs[0].doc_id, '%s/added.md' % INFRA_REF_ID)
    self.assertEqual(added_docs[1].doc_id, '%s/modified.md' % INFRA_REF_ID)

  def test_get_title(self):
    self.assertEqual('foo', docs.get_title(html('foo', 'bar')))
    self.assertEqual(None, docs.get_title('<bold>no title!</bold>'))
    self.assertEqual(None, docs.get_title('<title>broken title'))

  def test_pre_order_next(self):
    # /
    # |-a
    # |--b
    # |--c
    # |-d
    # |--e
    # |--f
    def children(p):
      if p == '/':
        return 'ad'
      elif p == '/a':
        return 'bc'
      elif p == '/d':
        return 'ef'
      else:
        return ''

    expected = [
      '/a',
      '/a/b',
      '/a/c',
      '/d',
      '/d/e',
      '/d/f',
      None,
    ]
    actual = []
    cur = '/'
    while cur != None:
      cur = docs.pre_order_next(cur, children)
      actual.append(cur)
    self.assertEqual(expected, actual)

def html(title, body):
  return (
      '<html><head><title>%s</title></head><body>%s</body></html>' %
      (title, body))
