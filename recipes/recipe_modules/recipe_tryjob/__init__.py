DEPS = [
  'build/file',
  'build/luci_config',

  'depot_tools/gclient',
  'depot_tools/git_cl',
  'depot_tools/bot_update',
  'depot_tools/tryserver',

  'recipe_engine/path',
  'recipe_engine/python',
  'recipe_engine/raw_io',
  'recipe_engine/step',
]


# TODO(phajdan.jr): provide coverage (http://crbug.com/693058).
DISABLE_STRICT_COVERAGE = True
