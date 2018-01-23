# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

DEPS = [
    'depot_tools/gsutil',
    'recipe_engine/context',
    'recipe_engine/file',
    'recipe_engine/path',
    'recipe_engine/platform',
    'recipe_engine/properties',
    'recipe_engine/python',
    'recipe_engine/step',
]


def RunSteps(api):
  build_dir = api.path['start_dir'].join('build_dir')
  try:
    version = api.properties['version']
    tar_filename = 'chromium-%s.tar.xz' % version
    tar_file = build_dir.join(tar_filename)
    api.gsutil.download_url('gs://chromium-browser-official/' + tar_filename,
                            tar_file)
    api.step('Extract tarball.',
             ['tar', '-xJf', str(tar_file), '-C',
              str(build_dir)])
    src_dir = build_dir.join('chromium-' + version)
    with api.context(cwd=src_dir):
      gn_args = [
          'is_debug=false',
          'enable_nacl=false',
      ]
      api.python('Download sysroot.',
                 api.path.join(src_dir, 'build', 'linux', 'sysroot_scripts',
                               'install-sysroot.py'), ['--arch=amd64'])
      api.python('Download clang.',
                 api.path.join(src_dir, 'tools', 'clang', 'scripts',
                               'update.py'),
                 ['--if-needed', '--without-android'])
      api.python('Bootstrap gn.',
                 api.path.join(src_dir, 'tools', 'gn', 'bootstrap',
                               'bootstrap.py'),
                 ['--gn-gen-args=%s' % ' '.join(gn_args)])
      api.python('Download nodejs.',
                 api.path.join(src_dir, 'third_party', 'depot_tools',
                               'download_from_google_storage.py'),
                 [
                     '--no_resume', '--extract', '--no_auth', '--bucket',
                     'chromium-nodejs/8.9.1', '-s',
                     'third_party/node/linux/node-linux-x64.tar.gz.sha1'
                 ])
      api.step('Build chrome.',
               ['ninja', '-C', 'out/Release', 'chrome/installer/linux'])
  finally:
    api.file.rmtree('Cleaning build dir.', build_dir)


def GenTests(api):
  yield (api.test('basic') + api.properties.generic(version='65.0.3318.0') +
         api.platform('linux', 64))

