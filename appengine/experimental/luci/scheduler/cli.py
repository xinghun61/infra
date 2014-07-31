# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import click
import json
import urllib
from httplib import HTTPConnection


def call(ctx, method, path, params = None, data = None):
  if params is None:
    params = {}
  params['uid'] = ctx.obj['uid']

  params_encoded = urllib.urlencode(params, True)
  fullpath = '%s?%s' % (path, params_encoded)

  conn = ctx.obj['conn']
  if data is not None:
    headers = {'Content-type': 'application/json'}
    conn.request(method, fullpath, json.dumps(data), headers)
  else:
    conn.request(method, fullpath)

  return conn.getresponse()

@click.group()
@click.option('--host', default='localhost')
@click.option('--port', default='8080')
@click.option('--uid', default='test_worker')
@click.pass_context
def cli(ctx, host, port, uid):
  url = '%s:%s' % (host, port)
  ctx.obj['conn'] = HTTPConnection(url)
  ctx.obj['uid'] = uid

@cli.command()
@click.pass_context
def get_all_jobs(ctx):
  resp = call(ctx, 'GET', '/api/v1/job')
  print resp.read()

@cli.command()
@click.option('--name', '-n', required=True)
@click.option('--binary', '-b', required=True)
@click.option('--param', '-p', multiple=True)
@click.pass_context
def add_job(ctx, name, binary, param):
  resp = call(ctx, 'POST', '/api/v1/job', data = {
    'name': name,
    'binary': binary,
    'param': list(param) or []
  })
  print resp.read()

@cli.command()
@click.pass_context
def delete_all_jobs(ctx):
  resp = call(ctx, 'DELETE', '/api/v1/job')
  print resp.read()

@cli.command()
@click.argument('job_id')
@click.pass_context
def delete_job(ctx, job_id):
  resp = call(ctx, 'DELETE', '/api/v1/job/%s' % job_id)
  print resp.read()

@cli.command()
@click.argument('job_id')
@click.pass_context
def get_job(ctx, job_id):
  resp = call(ctx, 'GET', '/api/v1/job/%s' % job_id)
  print resp.read()


if __name__ == '__main__':
  cli(obj = {})
