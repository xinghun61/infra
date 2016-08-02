# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from recipe_engine import config_types
from recipe_engine import recipe_api

COMMIT_MESSAGE = """Update submodule references.

This is an artificial commit to make dependencies specified in the DEPS file
visible to Codesearch.
This commit does not exist in the underlying repository."""


# Work around some assertions in config_types.Path.__init__.
class AbsolutePath(config_types.BasePath):
  def __init__(self, path):
    self._path = path

  def resolve(self, test_enabled):
    if test_enabled:
      return "[HACK]"
    return self._path  # pragma: no cover


class SyncSubmodulesApi(recipe_api.RecipeApi):
  def __call__(self, source, dest, source_ref='refs/heads/master',
               dest_ref='refs/heads/master'):
    # remote_run creates a temporary directory for our pwd, but that means big
    # checkouts get thrown away every build, and take 15 minutes to re-fetch
    # even from the cache.
    # The chromium_tests module seems to hack around this by using a
    # 'builder_cache' path, but it's not clear where that's defined.  The
    # infra_paths module mentions it, but I can't figure out where it's
    # instantiated or how it's used.
    # For now, hardcode an absolute path of '/b/build/slave/cache_dir/'.
    sanitized_buildername = ''.join(
        c if c.isalnum() else '_' for c in self.m.properties['buildername'])
    checkout_dir = config_types.Path(AbsolutePath('/b/build/slave/cache_dir/'),
                                     sanitized_buildername)
    self.m.file.makedirs('checkout', checkout_dir)
    self.m.path['checkout'] = checkout_dir

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
