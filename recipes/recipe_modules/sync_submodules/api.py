# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from recipe_engine import recipe_api

COMMIT_MESSAGE = """Update submodule references.

This is an artificial commit to make dependencies specified in the DEPS file
visible to Codesearch.
This commit does not exist in the underlying repository."""


def Humanish(url):
  if url.endswith('.git'):  # pragma: nocover
    url = url[:-4]
  slash = url.rfind('/')
  if slash != -1:
    url = url[slash + 1:]
  return url


class SyncSubmodulesApi(recipe_api.RecipeApi):
  def __call__(self, source, dest, source_ref='refs/heads/master',
               dest_ref='refs/heads/master'):
    # Subsequent git commands default to working in the 'checkout' directory.
    source_name = Humanish(source)
    checkout_dir = self.m.path['checkout'] = (
        self.m.path['cwd'].join(source_name))

    self.m.file.makedirs('checkout', checkout_dir)

    # Populate the git cache, get the path to the mirror.
    git_cache = self.m.path['git_cache']
    self.m.git(
        'cache', 'populate', '--cache-dir=%s' % git_cache, '--ignore-locks',
        source)
    mirror_dir = self.m.git(
        'cache', 'exists', '--cache-dir=%s' % git_cache, '--quiet', source,
        stdout=self.m.raw_io.output(),
        step_test_data=lambda:
            self.m.raw_io.test_api.stream_output('/foo')).stdout.strip()

    # Checkout the source repository.
    source_hash = self.m.git.checkout(
        mirror_dir, ref=source_ref, dir_path=checkout_dir, submodules=False)

    # Replace the remote, removing any old one that's still present.
    self.m.git('remote', 'remove', 'destination_repo', can_fail_build=False)
    self.m.git('remote', 'add', 'destination_repo', dest)

    # Fetch the destination ref.
    self.m.git('fetch', 'destination_repo', '+%s' % dest_ref)
    previous_hash = self.m.git(
        'rev-parse', 'FETCH_HEAD^',
        stdout=self.m.raw_io.output(),
        step_test_data=lambda:
            self.m.raw_io.test_api.stream_output('aabbccddee')).stdout.strip()

    # If we're up to date, don't do anything else.
    if previous_hash == source_hash:  # pragma: no cover
      return

    # Create submodule references.
    self.m.step('deps2submodules', [
        'python',
        self.resource('deps2submodules.py'),
        'DEPS',
    ], cwd=checkout_dir)

    # Commit and push to the destination ref.
    self.m.git('commit', '-m', COMMIT_MESSAGE)
    self.m.git('push', 'destination_repo', '+HEAD:%s' % dest_ref)
