#!/usr/bin/env python
# This file mocks typical recipes.py that normally runs a recipe.

import argparse
import json
import sys
import shutil

def main():
  parser = argparse.ArgumentParser()
  parser.add_argument('--output-result-json')
  parser.add_argument('--properties-file')
  args, _ = parser.parse_known_args()

  assert args.output_result_json
  assert args.properties_file

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

if __name__ == '__main__':
  sys.exit(main())