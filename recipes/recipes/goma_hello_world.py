# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Compiles trivial C++ program using Goma.

Intended to be used as a very simple litmus test of Goma health on LUCI staging
environment. Linux and OSX only.
"""


DEPS = [
  'build/goma',
  'recipe_engine/context',
  'recipe_engine/file',
  'recipe_engine/path',
  'recipe_engine/platform',
  'recipe_engine/properties',
  'recipe_engine/step',
  'recipe_engine/time',
]


HELLO_WORLD_CPP = """
#include <iostream>

int get_number();

int main() {
  std::cout << "Hello, world!" << std::endl;
  std::cout << "Non-static part " << get_number() << std::endl;
  return 0;
}
"""

MODULE_CPP = """
int get_number() {
  return %(time)d;
}
"""


def RunSteps(api):
  root_dir = api.path['tmp_base']

  # TODO(vadimsh): We need to somehow pull clang binaries and use them instead
  # of system-provided g++. Otherwise Goma may fall back to local execution,
  # since system-provided g++ may not be whitelisted in Goma.

  # One static object file and one "dynamic", to test cache hit and cache miss.
  source_code = {
    'hello_world.cpp': HELLO_WORLD_CPP,
    'module.cpp': MODULE_CPP % {'time': int(api.time.time())},
  }

  for name, data in sorted(source_code.items()):
    api.file.write_text('write %s' % name, root_dir.join(name), data)

  api.goma.ensure_goma(canary=True)
  api.goma.start()

  gomacc = api.goma.goma_dir.join('gomacc')
  out = root_dir.join('compiled_binary')
  build_exit_status = None

  try:
    # We want goma proxy to actually hit the backends, so disable fallback to
    # the local compiler.
    gomacc_env = {
      'GOMA_USE_LOCAL': 'false',
      'GOMA_FALLBACK': 'false',
    }
    with api.context(env=gomacc_env):
      objs = []
      for name in sorted(source_code):
        obj = root_dir.join(name.replace('.cpp', '.o'))
        api.step(
            'compile %s' % name,
            [gomacc, 'g++', '-c', root_dir.join(name), '-o', obj])
        objs.append(obj)
      api.step('link', [gomacc, 'g++', '-o', out] + objs)
      build_exit_status = 0
  except api.step.StepFailure as e:
    build_exit_status = e.retcode
    raise e
  finally:
    api.goma.stop(ninja_log_exit_status=build_exit_status)

  api.step('run', [out])


def GenTests(api):
  yield (
      api.test('linux') +
      api.platform.name('linux') +
      api.properties.generic(
          buildername='test_builder',
          mastername='test_master'))

  yield (
      api.test('linux_fail') +
      api.platform.name('linux') +
      api.properties.generic(
          buildername='test_builder',
          mastername='test_master') +
      api.step_data('link', retcode=1))
