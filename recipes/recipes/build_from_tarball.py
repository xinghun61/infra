# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

DEPS = [
    'depot_tools/depot_tools',
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
    # TODO(tandrii,thomasanderson): use ninja from CIPD package
    # https://chrome-infra-packages.appspot.com/p/infra/ninja
    with api.context(
        cwd=src_dir,
        env_suffixes={'PATH': [api.path.dirname(api.depot_tools.ninja_path)]}):
      llvm_bin_dir = src_dir.join('third_party', 'llvm-build',
                                  'Release+Asserts', 'bin')
      gn_bootstrap_env = {
          'CC': llvm_bin_dir.join('clang'),
          'CXX': llvm_bin_dir.join('clang++'),
          'AR': llvm_bin_dir.join('llvm-ar'),
          'LDFLAGS': '-fuse-ld=lld',
      }
      gn_args = [
          'is_debug=false',
          'enable_nacl=false',
          'is_official_build=true',
          'enable_distro_version_check=false',

          # TODO(thomasanderson): Setting use_system_libjpeg shouldn't be
          # necessary when unbundling libjpeg.
          'use_system_libjpeg=true',
          'use_v8_context_snapshot=false',
      ]
      unbundle_libs = [
          'fontconfig',
          'freetype',
          'libdrm',
          'libjpeg',
          'libwebp',
          'opus',
          'snappy',

          # https://crbug.com/731766
          # 'ffmpeg',

          # TODO(thomasanderson): Add ogg-dev to sysroots.
          # 'flac',

          # TODO(thomasanderson): Reenable once Debian unstable pulls in
          # harfbuzz 1.7.5 or later.
          # 'harfbuzz-ng',

          # The icu dev package is huge, so it's omitted from the sysroots.
          # 'icu',

          # https://crbug.com/752403#c10
          # 'libpng',

          # TODO(thomasanderson): Update the sysroot.
          # 'libvpx',

          # https://crbug.com/736026
          # 'libxml',

          # TODO(thomasanderson): Add libxml2-dev to sysroots.
          # 'libxslt',

          # Chrome passes c++ strings to re2, but the inline namespace used by
          # libc++ (std::__1::string) differs from the one re2 expects
          # (std::__cxx11::string), causing link failures.
          # 're2',

          # Use the yasm in third_party to prevent having to install yasm on the
          # bot.
          # 'yasm',

          # TODO(thomasanderson): Add libminizip-dev to sysroots.
          # 'zlib',
      ]
      api.python(
          'Download sysroot.',
          api.path.join(src_dir, 'build', 'linux', 'sysroot_scripts',
                        'install-sysroot.py'), ['--arch=amd64'])

      clang_update_args = [
          '--force-local-build', '--without-android', '--skip-checkout'
      ]
      if [int(x) for x in version.split('.')] >= [71, 0, 3551, 0]:
        clang_update_args.append('--without-fuchsia')
      api.python(
          'Build clang.',
          api.path.join(src_dir, 'tools', 'clang', 'scripts', 'update.py'),
          clang_update_args)

      gn_bootstrap_args = [
          '--gn-gen-args=%s' % ' '.join(gn_args), '--use-custom-libcxx'
      ]
      with api.context(env=gn_bootstrap_env):
        api.python(
            'Bootstrap gn.',
            api.path.join(src_dir, 'tools', 'gn', 'bootstrap', 'bootstrap.py'),
            gn_bootstrap_args)
      api.python(
          'Download nodejs.',
          api.path.join(src_dir, 'third_party', 'depot_tools',
                        'download_from_google_storage.py'), [
                            '--no_resume', '--extract', '--no_auth', '--bucket',
                            'chromium-nodejs/8.9.1', '-s',
                            'third_party/node/linux/node-linux-x64.tar.gz.sha1'
                        ])
      api.python(
          'Unbundle libraries.',
          api.path.join(src_dir, 'build', 'linux', 'unbundle',
                        'replace_gn_files.py'),
          ['--system-libraries'] + unbundle_libs)
      api.step('Build chrome.',
               ['ninja', '-C', 'out/Release', 'chrome/installer/linux'])
  finally:
    api.file.rmtree('Cleaning build dir.', build_dir)


def GenTests(api):
  yield (api.test('basic') + api.properties.generic(version='69.0.3491.0') +
         api.platform('linux', 64))
  yield (api.test('clang-no-fuchsia') + api.properties.generic(
      version='71.0.3551.0') + api.platform('linux', 64))
  yield (api.test('basic-gn-without-sysroot') + api.properties.generic(
      version='72.0.3610.0') + api.platform('linux', 64))
