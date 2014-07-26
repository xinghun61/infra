# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections
import json
import logging
import os
import sys
import tempfile

from cStringIO import StringIO

import expect_tests

from infra.libs import git2
from infra.libs.git2 import data
from infra.services.gnumbd import gnumbd
from infra.services.gnumbd.test import gnumbd_test_definitions


BASE_PATH = os.path.dirname(os.path.abspath(__file__))


# TODO(iannucci): Make these first class data library objects
class GitEntry(object):
  typ  = None
  mode = None

  def intern(self, repo):
    raise NotImplementedError()  # pragma: no cover


class GitFile(GitEntry):
  typ = 'blob'

  def __init__(self, content, mode=0644):
    super(GitFile, self).__init__()
    self.content = content
    assert mode in (0644, 0664, 0755)
    self.mode = '0100%o' % mode

  def intern(self, repo):
    return repo.intern(self.content)


class GitTree(GitEntry):
  typ = 'tree'
  mode = '0040000'

  def __init__(self, entries):
    super(GitTree, self).__init__()
    assert all(
        isinstance(k, str) and isinstance(v, GitEntry)
        for k, v in entries.iteritems()
    )
    self.entries = entries

  def intern(self, repo):
    with tempfile.TemporaryFile() as tf:
      for path, entry in self.entries.iteritems():
        tf.write('%s %s %s\t%s' %
                 (entry.mode, entry.typ, entry.intern(repo), path))
      tf.seek(0)
      return repo.run('mktree', '-z', stdin=tf).strip()

class TestRef(git2.Ref):
  def synthesize_commit(self, message, number=None, tree=None, svn=False,
                        footers=None):
    footers = footers or collections.OrderedDict()
    if number is not None:
      if svn:
        footers[gnumbd.GIT_SVN_ID] = [
            'svn://repo/path@%s 0039d316-1c4b-4281-b951-d872f2087c98' % number]
      else:
        footers[gnumbd.COMMIT_POSITION] = [
            gnumbd.FMT_COMMIT_POSITION(self, number)]

    commit = self.repo.synthesize_commit(self.commit, message, footers=footers,
                                         tree=tree)
    self.update_to(commit)
    return commit


class TestClock(object):
  def __init__(self):
    self._time = 1402589336

  def time(self):
    self._time += 10
    return self._time


class TestConfigRef(gnumbd.GnumbdConfigRef):
  def update(self, **values):
    new_config = self.current
    new_config.update(values)
    self.ref.synthesize_commit(
        'update(%r)' % values.keys(),
        tree=GitTree({'config.json': GitFile(json.dumps(new_config))}))


class TestRepo(git2.Repo):
  def __init__(self, short_name, clock, mirror_of=None):
    super(TestRepo, self).__init__(mirror_of or 'local test repo')
    self._short_name = short_name
    self.repos_dir = tempfile.tempdir

    if mirror_of is None:
      self._repo_path = tempfile.mkdtemp(suffix='.git')
      self.run('init', '--bare')

    self._clock = clock

  # pylint: disable=W0212
  repo_path = property(lambda self: self._repo_path)

  def __getitem__(self, refstr):
    return TestRef(self, refstr)

  def synthesize_commit(self, parent, message, tree=None, footers=None):
    tree = tree or GitTree({'file': GitFile('contents')})
    tree = tree.intern(self) if isinstance(tree, GitTree) else tree
    assert isinstance(tree, str)

    parents = [parent.hsh] if parent is not git2.INVALID else []

    timestamp = data.CommitTimestamp(self._clock.time(), '+', 8, 0)
    user = data.CommitUser('Test User', 'test_user@example.com', timestamp)

    return self.get_commit(self.intern(data.CommitData(
        tree, parents, user, user, (), message.splitlines(),
        data.CommitData.merge_lines([], footers or {})
    ), 'commit'))

  def snap(self, include_committer=False, include_config=False):
    ret = {}
    if include_committer:
      fmt = '%H%x00committer %cn <%ce> %ci%n%n%B%x00%x00'
    else:
      fmt = '%H%x00%B%x00%x00'
    for ref in (r.ref for r in self.refglob('*')):
      if ref == gnumbd.GnumbdConfigRef.REF and not include_config:
        continue
      log = self.run('log', ref, '--format=%s' % fmt)
      ret[ref] = collections.OrderedDict(
          (commit, message.splitlines())
          for commit, message in (
              r.split('\0') for r in log.split('\0\0\n') if r)
      )
    return ret

  def __repr__(self):
    return 'TestRepo(%r)' % self._short_name


def RunTest(test_name):
  ret = []
  clock = TestClock()
  origin = TestRepo('origin', clock)
  local = TestRepo('local', clock, origin.repo_path)

  cref = TestConfigRef(origin)
  cref.update(enabled_refglobs=['refs/heads/*'], interval=0)

  def checkpoint(message, include_committer=False, include_config=False):
    ret.append([message, {'origin': origin.snap(include_committer,
                                                include_config)}])

  def run(include_log=True):
    stdout = sys.stdout
    stderr = sys.stderr

    if include_log:
      logout = StringIO()
      root_logger = logging.getLogger()
      log_level = root_logger.getEffectiveLevel()
      shandler = logging.StreamHandler(logout)
      shandler.setFormatter(
          logging.Formatter('%(levelname)s: %(message)s'))
      root_logger.addHandler(shandler)
      root_logger.setLevel(logging.INFO)

    try:
      sys.stderr = sys.stdout = open(os.devnull, 'w')
      local.reify()
      gnumbd.inner_loop(local, cref, clock)
    except Exception:  # pragma: no cover
      import traceback
      ret.append(traceback.format_exc().splitlines())
    finally:
      sys.stdout = stdout
      sys.stderr = stderr

      if include_log:
        root_logger.removeHandler(shandler)
        root_logger.setLevel(log_level)
        ret.append({'log output': logout.getvalue().splitlines()})

  gnumbd_test_definitions.GNUMBD_TESTS[test_name](
      origin, local, cref, run, checkpoint)

  return expect_tests.Result(ret)


@expect_tests.test_generator
def GenTests():
  for test_name, test in gnumbd_test_definitions.GNUMBD_TESTS.iteritems():
    yield expect_tests.Test(
        __package__ + '.' + test_name,
        expect_tests.FuncCall(RunTest, test_name),
        expect_base=test_name, ext='yaml', break_funcs=[test],
        covers=(
            expect_tests.Test.covers_obj(RunTest) +
            expect_tests.Test.covers_obj(gnumbd_test_definitions)
        ))
