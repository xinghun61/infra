# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""
This recipe is meant to be run in response to changes to "luci-go".

It is responsible for examining the contents of the "web/" directory's external
dependencies (Bower, Node.JS) and, if they have changed, performing a new
checkout and bundling it into a CIPD package.

These CIPD packages will then be consumed by "web.py" for deterministic, pinned
installations.
"""

import collections
import hashlib


DEPS = [
    'depot_tools/gclient',
    'depot_tools/bot_update',
    'depot_tools/cipd',
    'build/file',
    'recipe_engine/context',
    'recipe_engine/path',
    'recipe_engine/python',
    'recipe_engine/step',
]


WebPackageSpec = collections.namedtuple('WebPackageSpec',
    ('filename', 'relpath', 'cipd_package'))


_WEB_PACKAGES = {
    'bower.js': WebPackageSpec(
        filename='bower.json',
        relpath=('inc', 'bower_components'),
        cipd_package='infra/luci/web/bower-deps'),
    'node.js': WebPackageSpec(
        filename='package.json',
        relpath=('node_modules',),
        cipd_package='infra/luci/web/node-deps'),
}


def _hash_content(content):
  return hashlib.sha256(content).hexdigest()


def RunSteps(api):
  api.gclient.set_config('luci_go')
  api.bot_update.ensure_checkout()
  web_path = api.path['checkout'].join(
      'go', 'src', 'github.com', 'luci', 'luci-go', 'web')

  # Install "Node.js" package from CIPD.
  prereq_dir = api.path['start_dir'].join('cipd')
  api.cipd.ensure(prereq_dir, {
      'infra/nodejs/nodejs/${platform}': 'node_version:4.5.0',
  })

  # Always run "build.py" to ensure that "web/" can be provisioned.
  env = {
      'PATH': api.path.pathsep.join([str(prereq_dir), '%(PATH)s']),
  }
  with api.context(env=env):
    api.python(
        'provision web deps',
        web_path.join('web.py'),
        args=['install'],
    )

  for name, spec in sorted(_WEB_PACKAGES.iteritems()):
    with api.step.nest(name):
      content = api.file.read(
          'read',
          web_path.join(spec.filename))
      result = api.step.active_result

      h = _hash_content(content)
      result.presentation.step_text += 'hash: %s' % (h,)

      result = api.cipd.search(spec.cipd_package, 'content_hash:%s' % (h,))
      if len(result.json.output['result']) > 0:
        result.presentation.step_text += 'Package exists!'
        continue

      content_path = web_path.join(*spec.relpath)
      pkg = api.cipd.PackageDefinition(
          spec.cipd_package, content_path, install_mode='copy')
      pkg.add_dir(content_path)
      api.cipd.create_from_pkg(pkg, tags={'content_hash': h})


def GenTests(api):
  def _cipd_search_step(name):
    pkg = _WEB_PACKAGES[name]
    return '%s.cipd search %s content_hash:%s' % (
        name, pkg.cipd_package, _hash_content(''))

  yield (
    api.test('basic') +
    api.override_step_data(
        _cipd_search_step('bower.js'),
        api.cipd.example_search('infra/luci/web/bower-deps', instances=0)) +
    api.override_step_data(
        _cipd_search_step('node.js'),
        api.cipd.example_search('infra/luci/web/node-deps', instances=0))
  )

  yield (
    api.test('no_rolls')
  )
