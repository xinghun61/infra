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
          'enable_distro_version_check=false',
          'use_system_libjpeg=true',  # TODO(thomasanderson): This shouldn't be
                                      # necessary when unbundling libjpeg.
      ]
      unbundle_libs = [
          # 'ffmpeg',  # https://crbug.com/731766
          # 'flac',  # TODO(thomasanderson): Add ogg-dev to sysroots.
          'fontconfig',
          'freetype',
          # 'harfbuzz-ng',  # TODO(thomasanderson): Reenable once Debian
                            # unstable pulls in harfbuzz 1.7.5 or later.
          # 'icu',  # The icu dev package is huge, so it's omitted from the
                    # sysroots.
          'libdrm',
          'libjpeg',
          # 'libpng',  # https://crbug.com/752403#c10
          # 'libvpx',  # TODO(thomasanderson): Update the sysroot.
          'libwebp',
          # 'libxml',  # https://crbug.com/736026
          # 'libxslt',  # TODO(thomasanderson): Add libxml2-dev to sysroots.
          'opus',
          # 're2',  # Chrome passes c++ strings to re2, but the inline namespace
                    # used by libc++ (std::__1::string) differs from the one re2
                    # expects (std::__cxx11::string), causing link failures.
          'snappy',
          'yasm',
          # 'zlib',  # TODO(thomasanderson): Add libminizip-dev to sysroots.
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
          'ninja', '-C', 'out/Release', 'chrome/installer/linux'
      ])
  finally:
    api.file.rmtree('Cleaning build dir.', build_dir)


def GenTests(api):
  yield (api.test('basic') + api.properties.generic(version='65.0.3318.0') +
         api.platform('linux', 64))
