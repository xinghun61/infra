# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from appengine_module.testing_utils import testing
from appengine_module.cr_rev import app
from appengine_module.cr_rev.test import model_helpers


class TestViews(testing.AppengineTestCase):
  app_module = app.app

  def test_main_page(self):
    """Test that the root page renders."""
    response = self.test_app.get('/')
    self.assertEquals('200 OK', response.status)

  def test_warmup(self):
    """Test that the warmup page renders."""
    response = self.test_app.get('/_ah/warmup')
    self.assertEquals('200 OK', response.status)

  def test_start(self):
    """Test that the start page renders."""
    response = self.test_app.get('/_ah/start')
    self.assertEquals('200 OK', response.status)

  def test_404(self):
    """Test that an unknown number 404s."""
    response = self.test_app.get('/12345', status=404)
    self.assertEquals('404 Not Found', response.status)

  def test_redirect_referer(self):
    """Test that adding a referer doesn't break anything."""
    response = self.test_app.get('/10000000', status=302,
        headers=[('Referer', 'https://coolinternet.blog')])
    self.assertEqual(
        response.location,
        'https://codereview.chromium.org/10000000')

  def test_redirect_paths(self):
    """Test that a redirect retains extra path information."""
    response = self.test_app.get('/10000000/bananas', status=302)
    self.assertEqual(
        response.location,
        'https://codereview.chromium.org/10000000/bananas')

  def test_redirect_query_string(self):
    """Test that a redirect retains any query strings."""
    response = self.test_app.get('/10000000/bananas?cool_mode=on', status=302)
    self.assertEqual(
        response.location,
        'https://codereview.chromium.org/10000000/bananas?cool_mode=on')

  def test_redirect_rietveld(self):
    """Test that rietveld issues are recognized and redirected."""
    response = self.test_app.get('/10000000', status=302)
    self.assertEqual(
        response.location,
        'https://codereview.chromium.org/10000000')

  def test_redirect_number(self):
    """Test that a stored number redirects properly."""
    my_repo = model_helpers.create_repo()
    my_repo.put()
    my_commit = model_helpers.create_commit()
    my_commit.put()
    my_numberings = model_helpers.create_numberings()
    my_numberings[0].numbering_identifier = 'svn://svn.chromium.org/chrome'
    for numbering in my_numberings:
      numbering.put()

    response = self.test_app.get('/100', status=302)
    self.assertEqual(
        response.location,
        'https://crrev.com/%s' % ('b0b1beef' * 5,))

  def test_redirect_numeric_git_sha(self):
    """Test that a stored numeric git_sha redirects properly."""
    my_repo = model_helpers.create_repo()
    my_repo.put()
    my_commit = model_helpers.create_commit()
    my_commit.git_sha = '11111111' * 5
    my_commit.redirect_url = 'https://crrev.com/%s' % my_commit.git_sha
    my_commit.put()
    response = self.test_app.get('/%s' % ('11111111' * 5,), status=302)
    self.assertEqual(
        response.location,
        my_commit.redirect_url)

  def test_redirect_git_sha(self):
    """Test that a stored git_sha redirects properly."""
    my_repo = model_helpers.create_repo()
    my_repo.put()
    my_commit = model_helpers.create_commit()
    my_commit.put()
    my_numberings = model_helpers.create_numberings()
    my_numberings[0].numbering_identifier = 'svn://svn.chromium.org/chrome'
    for numbering in my_numberings:
      numbering.put()

    response = self.test_app.get('/%s' % ('b0b1beef' * 5,), status=302)
    self.assertEqual(
        response.location,
        my_commit.redirect_url)

  def test_redirect_short_git_sha(self):
    """Test that a short git_sha is sent to chromium/src."""
    response = self.test_app.get('/deadbeef', status=302)
    self.assertEqual(
        response.location,
        'https://chromium.googlesource.com/chromium/src/+/deadbeef')
