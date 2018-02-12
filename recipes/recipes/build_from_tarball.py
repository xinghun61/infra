# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

DEPS = [
    'build/goma',
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
    api.goma.ensure_goma(canary=True)
    api.goma.start()

    version = api.properties['version']
    tar_filename = 'chromium-%s.tar.xz' % version
    tar_file = build_dir.join(tar_filename)
    api.gsutil.download_url('gs://chromium-browser-official/' + tar_filename,
                            tar_file)
    api.step('Extract tarball.',
             ['tar', '-xJf', str(tar_file), '-C',
              str(build_dir)])
    src_dir = build_dir.join('chromium-' + version)
    with api.context(cwd=src_dir, env={'GOMA_USE_LOCAL': 'false'}):
      llvm_bin_dir = src_dir.join('third_party', 'llvm-build',
                                  'Release+Asserts', 'bin')
      gn_bootstrap_env = {
          'CC': llvm_bin_dir.join('clang'),
          'CXX': llvm_bin_dir.join('clang++'),
          'LD': llvm_bin_dir.join('lld'),
          'AR': llvm_bin_dir.join('llvm-ar'),
      }
      gn_args = [
          'is_debug=false',
          'enable_nacl=false',
          'is_official_build=true',
          'use_goma=true',
          'goma_dir="%s"' % api.goma.goma_dir,
      ]
      unbundle_libs = [
          # 'ffmpeg',  # https://crbug.com/731766
          # 'flac',  # TODO(thomasanderson): Add libflac-dev to the sysroots.
          'fontconfig',
          'freetype',
          # 'harfbuzz-ng',  # TODO(thomasanderson): Update to the debian sid
                            # sysroot.
          # 'icu',  # TODO(thomasanderson): Add libicu-dev to the sysroots.
          # 'libdrm',  # TODO(thomasanderson): Update to the debian sid sysroot.
          # 'libjpeg',  # TODO(thomasanderson): Add libjpeg62-turbo-dev to the
                        # sysroots.
          # 'libpng',  # https://crbug.com/752403#c10
          # 'libvpx',  # TODO(thomasanderson): Add libvpx-dev to the sysroots.
          # 'libwebp',  # TODO(thomasanderson): Add libwebp-dev to the sysroots.
          # 'libxml',  # https://crbug.com/736026
          # 'libxslt', # TODO(thomasanderson): Add libxslt1-dev to the sysroots.
          # 'opus',  # TODO(thomasanderson): Add libopus-dev to the sysroots.
          # 're2',  # TODO(thomasanderson): Add libre2-dev to the sysroots.
          # 'snappy',  # TODO(thomasanderson): Add libsnappy-dev to the
                       # sysroots.
          'yasm',
          # 'zlib',  # TODO(thomasanderson): Update to the debian sid sysroot.
      ]
      api.python('Download sysroot.',
                 api.path.join(src_dir, 'build', 'linux', 'sysroot_scripts',
                               'install-sysroot.py'), ['--arch=amd64'])
      api.python('Build clang.',
                 api.path.join(src_dir, 'tools', 'clang', 'scripts',
                               'update.py'), [
                                   '--force-local-build', '--if-needed',
                                   '--without-android', '--skip-checkout'
                               ])
      with api.context(env=gn_bootstrap_env):
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
      api.python('Unbundle libraries.',
                 api.path.join(src_dir, 'build', 'linux', 'unbundle',
                               'replace_gn_files.py'),
                 ['--system-libraries'] + unbundle_libs)
      api.step('Build chrome.', [
          'ninja', '-C', 'out/Release', '-j', '50', 'chrome/installer/linux'
      ])
  finally:
    api.file.rmtree('Cleaning build dir.', build_dir)


def GenTests(api):
  yield (api.test('basic') + api.properties.generic(version='65.0.3318.0') +
         api.platform('linux', 64))
