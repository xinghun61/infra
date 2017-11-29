#!/usr/bin/env python
# This file mocks typical recipes.py that normally runs a recipe.

import argparse
import json
import os
import shutil
import socket
import sys
import urllib
import urllib2


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
    # Git is enabled only in Swarming mode.
    if os.environ.get('SWARMING_TASK_ID'):
      assert get_git_email() == 'system@example.com', get_git_email()
    return 0

  assert args.command == 'run'
  assert args.output_result_json
  assert args.properties_file

  # Actual recipe execution happens under the recipe account. See
  # localauth.Server config in cook_test.go.
  assert get_current_account() == 'recipe_acc', get_current_account()
  if os.environ.get('SWARMING_TASK_ID'):
    assert get_git_email() == 'recipe@example.com', get_git_email()
    assert get_gsutil_token() == 'fake_recipe_acc_token', get_gsutil_token()
    if sys.platform != 'win32':
      assert get_devshell_email() == 'recipe@example.com', get_devshell_email()

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


def get_git_email():
  home = os.environ['INFRA_GIT_WRAPPER_HOME']
  with open(os.path.join(home, '.gitconfig'), 'rt') as f:
    cfg = f.read()
  for line in cfg.splitlines():
    line = line.strip()
    if line.startswith('email = '):
      return line[len('email = '):]
  return None


def get_devshell_email():
  port = int(os.environ['DEVSHELL_CLIENT_PORT'])
  sock = socket.socket()
  sock.connect(('localhost', port))

  data = '[]'
  sock.sendall('%s\n%s' % (len(data), data))

  header = sock.recv(6).decode()
  assert '\n' in header
  len_str, json_str = header.split('\n', 1)
  to_read = int(len_str) - len(json_str)
  if to_read > 0:
    json_str += sock.recv(to_read)

  pbl = json.loads(json_str)
  assert isinstance(pbl, list)

  pbl_len = len(pbl)
  return pbl[0] if pbl_len > 0 else None


def get_gsutil_token():
  cfg = {}
  with open(os.environ['BOTO_CONFIG'], 'rt') as f:
    for line in f:
      if '=' in line:
        k, v = line.split('=')
        cfg[k.strip()] = v.strip()

  data = urllib.urlencode({
    'grant_type': 'refresh_token',
    'refresh_token': cfg['gs_oauth2_refresh_token'],
    'client_id': 'fake',
    'client_secret': 'fake',
  })

  req = urllib2.Request(cfg['provider_token_uri'], data)
  token = json.loads(urllib2.urlopen(req).read())
  return token['access_token']


if __name__ == '__main__':
  sys.exit(main())
