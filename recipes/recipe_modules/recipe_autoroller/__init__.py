DEPS = [
  'build/luci_config',
  'build/gsutil',

  'depot_tools/cipd',
  'depot_tools/gclient',
  'depot_tools/git',
  'depot_tools/git_cl',

  'recipe_engine/json',
  'recipe_engine/path',
  'recipe_engine/python',
  'recipe_engine/raw_io',
  'recipe_engine/step',
  'recipe_engine/tempfile',
  'recipe_engine/time',
]


# TODO(phajdan.jr): provide coverage (http://crbug.com/693058).
DISABLE_STRICT_COVERAGE = True
