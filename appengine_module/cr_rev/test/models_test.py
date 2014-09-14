# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json

from appengine_module.testing_utils import testing

from google.appengine.ext import ndb

from appengine_module.cr_rev import models
from appengine_module.cr_rev.test import model_helpers


class TestModels(testing.AppengineTestCase):
  def test_svn_id(self):
    expected = json.dumps({
      'repo': 'svn://test',
      'revision': 100,
      'type': 'svn'
      },
      sort_keys=True
    )
    generated = models.NumberingMap.svn_unique_id('svn://test', 100)
    self.assertEquals(generated, expected)

  def test_git_id(self):
    expected = json.dumps({
      'project': 'test',
      'repo': 'testing/src',
      'ref': 'refs/heads/master',
      'commit_pos': 100,
      'type': 'git'
      },
      sort_keys=True
    )
    generated = models.NumberingMap.git_unique_id(
        'test', 'testing/src', 'refs/heads/master', 100)
    self.assertEquals(generated, expected)

  def test_unique_id_svn(self):
    expected = json.dumps({
      'repo': 'svn://test',
      'revision': 100,
      'type': 'svn'
      },
      sort_keys=True
    )
    generated = models.NumberingMap.unique_id(
        100, models.NumberingType.SVN, ref='svn://test')
    self.assertEquals(generated, expected)

  def test_unique_id_git(self):
    expected = json.dumps({
      'project': 'test',
      'repo': 'testing/src',
      'ref': 'refs/heads/master',
      'commit_pos': 100,
      'type': 'git'
      },
      sort_keys=True
    )
    generated = models.NumberingMap.unique_id(
        100, models.NumberingType.COMMIT_POSITION, project='test',
        repo='testing/src', ref='refs/heads/master')
    self.assertEquals(generated, expected)

  def test_numbering_key(self):
    expected = ndb.Key(
        models.NumberingMap,
        json.dumps({
          'project': 'test',
          'repo': 'testing/src',
          'ref': 'refs/heads/master',
          'commit_pos': 100,
          'type': 'git'
          },
          sort_keys=True
        )
    )
    generated = models.NumberingMap.get_key_by_id(
        100, models.NumberingType.COMMIT_POSITION, project='test',
        repo='testing/src', ref='refs/heads/master')
    self.assertEquals(generated, expected)

  def test_numbering_put_hooks(self):
    """Test that they key is set automatically when you put()."""
    my_numberings = model_helpers.create_numberings()
    for numbering in my_numberings:
      expected = models.NumberingMap.get_key_by_id(
          numbering.number, numbering.numbering_type, repo=numbering.repo,
          project=numbering.project, ref=numbering.numbering_identifier)
      generated = numbering.put()

      self.assertEquals(generated, expected)

  def test_repo_id(self):
    expected = json.dumps({
      'project': 'test',
      'repo': 'testing/src',
      },
      sort_keys=True
    )
    generated = models.Repo.repo_id('test', 'testing/src')
    self.assertEquals(generated, expected)

  def test_repo_key(self):
    expected = ndb.Key(
        models.Repo,
        json.dumps({
          'project': 'test',
          'repo': 'testing/src',
          },
          sort_keys=True
        )
    )
    generated = models.Repo.get_key_by_id('test', 'testing/src')
    self.assertEquals(generated, expected)

  def test_repo_put_hooks(self):
    """Test that they key is set automatically when you put()."""
    expected = models.Repo.get_key_by_id('cool', 'cool_src')
    generated = model_helpers.create_repo().put()
    self.assertEquals(generated, expected)

  def test_revision_put_hooks(self):
    my_commit = model_helpers.create_commit()
    generated = my_commit.put()
    expected = ndb.Key(models.RevisionMap, my_commit.git_sha)
    self.assertEquals(generated, expected)
