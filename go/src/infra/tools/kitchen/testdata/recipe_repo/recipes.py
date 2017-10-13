#!/usr/bin/env python
# This file mocks typical recipes.py that normally runs a recipe.

import argparse
import json
import os
import shutil
import sys


def main():
  parser = argparse.ArgumentParser()
  parser.add_argument('--operational-args-path')

  subparsers = parser.add_subparsers()
  fetch_cmd = subparsers.add_parser('fetch')
  fetch_cmd.set_defaults(command='fetch')

  run_cmd = subparsers.add_parser('run')
  run_cmd.add_argument('--output-result-json')
  run_cmd.add_argument('--properties-file')
  run_cmd.set_defaults(command='run')

  args, _ = parser.parse_known_args()

  if args.command == 'fetch':
    # Fetch happens under the system account. See localauth.Server config in
    # cook_test.go.
    assert get_current_account() == 'system_acc', get_current_account()
    return 0

  assert args.command == 'run'
  assert args.output_result_json
  assert args.properties_file

  # Actual recipe execution happens under the recipe account. See
  # localauth.Server config in cook_test.go.
  assert get_current_account() == 'recipe_acc', get_current_account()

  with open(args.properties_file) as f:
    properties = json.load(f)
  cfg = properties.pop('recipe_mock_cfg')

  with open(cfg['input_path'], 'w') as f:
    json.dump({
      'args': sys.argv,
      'properties': properties,
    }, f)

  mocked_result_path = cfg.get('mocked_result_path')
  if mocked_result_path:
    shutil.copyfile(mocked_result_path, args.output_result_json)
  return cfg['exitCode']


def get_current_account():
  with open(os.environ['LUCI_CONTEXT'], 'rt') as f:
    lc = json.load(f)
  return lc["local_auth"]["default_account_id"]


if __name__ == '__main__':
  sys.exit(main())
