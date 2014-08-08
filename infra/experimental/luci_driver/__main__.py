#!/usr/bin/env python
# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
import json
import logging
import random
import sys
import time

from multiprocessing import Process, current_process

import requests


LOGGER = logging.getLogger(__name__)


def gen_simple_deps(fanout, depth):
  """Create pseudorandom fake dependency graphs."""
  graph = {
      'deadbeefdeadbeefdeadbeefdeadbeefdeadbeef':
          ['baddecafbaddecafbaddecafbaddecafbaddecaf',
           'cafebabecafebabecafebabecafebabecafebabe'],
      'baddecafbaddecafbaddecafbaddecafbaddecaf':
          ['f005ba11f005ba11f005ba11f005ba11f005ba11'],
      'cafebabecafebabecafebabecafebabecafebabe':
          ['f005ba11f005ba11f005ba11f005ba11f005ba11'],
  }
  roots = ['deadbeefdeadbeefdeadbeefdeadbeefdeadbeef']
  return graph, roots


def gen_deps(fanout, depth, density):
  """Create pseudorandom fake dependency graphs."""
  nodes = set()
  roots = set()
  graph = {}
  ranks = random.randint(int(depth * 0.5), int(depth * 1.5))
  for _ in xrange(ranks):
    width = random.randint(int(fanout * 0.5), int(fanout * 1.5))
    new_nodes = ['%040x' % random.randrange(16**40) for _ in xrange(width)]
    roots.update(new_nodes)
    for i in nodes:
      for j in new_nodes:
        if random.random() < density:
          graph.setdefault(i, []).append(j)
          roots.discard(j)
    nodes.update(new_nodes)
  return graph, roots


def post_jobs(url, jobs):
  """Post initial collection of jobs to the scheduler."""
  job_url = '%s/api/v1/job' % url
  for job in jobs:
    params = {'uid': 'seeder'}
    data = {'name': job[:8], 'binary': job, 'version': 0}
    r = requests.post(job_url, params=params, data=json.dumps(data))
    if r.status_code != requests.codes.ok or r.json()['status'] != 'OK':
      LOGGER.error('Failed to post initial job %s: %r', job, r._content)
      continue
    LOGGER.debug('Posted initial job %s', job)


def fake_slave(url, graph):
  """Run a fake slave worker.

  Performs the following actions, in order:
  * Heartbeat
  * Acquire a job
  * Sleep
  * Either:
    * Complete job; or
    * Halt job with some number of dependencies
  * Rinse (sleep)
  * Repeat

  Whether the job completes or halts with dependencies is determined by the
  |graphs| input argument. This is a collection of pre-generated dependency
  DAGs (represented as nodes mapped to a list of their children). When the
  slave worker picks up a job, it emits dependencies based on the children of
  that job found in the graph. If the job has no children, it is completed.

  The slave worker exits when it fails to acquire a job three consecutive times.
  """
  worker_id = current_process().name
  LOGGER.debug('Hello from worker %s', worker_id)
  uid = {'uid': worker_id}
  heartbeat_url = '%s/api/v1/worker/heartbeat' % (url)
  acquire_url = '%s/api/v1/worker/acquire_job' % (url)
  job_url = '%s/api/v1/job' % (url)

  failures_left = 3
  while failures_left:
    r = requests.post(heartbeat_url, params=uid)
    LOGGER.debug('Sent request %s %s', r.request.url, r.request.body)
    if r.status_code != requests.codes.ok or r.json()['status'] != 'OK':
      LOGGER.error('%s failed to send heartbeat: %r', worker_id, r._content)
      failures_left -= 1
      continue

    r = requests.post(acquire_url, params=uid)
    LOGGER.debug('Sent request %s %s', r.request.url, r.request.body)
    if r.status_code != requests.codes.ok or r.json()['status'] != 'OK':
      LOGGER.error('%s failed to acquire job: %r', worker_id, r._content)
      failures_left -= 1
      continue
    job = r.json()['result']['job']
    LOGGER.info('%s acquired job %s', worker_id, job['name'])

    failures_left = 3
    time.sleep(random.uniform(0, 2))

    children = graph.get(job['binary'])
    if children:
      deps = []
      for dep in children:
        data = {'name': dep[:8], 'binary': dep, 'version': 0}
        r = requests.post(job_url, params=uid, data=json.dumps(data))
        LOGGER.debug('Sent request %s %s', r.request.url, r.request.body)
        if r.status_code != requests.codes.ok or r.json()['status'] != 'OK':
          LOGGER.error('Failed to post dependency %s: %r', dep, r._content)
          continue
        LOGGER.debug('Posted dependency %s', dep)
        deps.append(r.json()['result']['job']['id'])

      data = {'state': 'queued', 'dependencies': deps}
      r = requests.put('%s/%s' % (job_url, job['id']),
                       params=uid, data=json.dumps(data))
      LOGGER.debug('Sent request %s %s', r.request.url, r.request.body)
      if r.status_code != requests.codes.ok or r.json()['status'] != 'OK':
        LOGGER.error('%s failed to halt job: %r', worker_id, r._content)
        continue
      LOGGER.info('%s halted job %s', worker_id, job)

    else:
      data = {'state': 'completed'}
      r = requests.put('%s/%s' % (job_url, job['id']),
                       params=uid, data=json.dumps(data))
      LOGGER.debug('Sent request %s %s', r.request.url, r.request.body)
      if r.status_code != requests.codes.ok or r.json()['status'] != 'OK':
        LOGGER.error('%s failed to complete job: %r', worker_id, r._content)
        continue
      LOGGER.info('%s completed job %s', worker_id, job)

    time.sleep(random.uniform(0, 2))


def parse_args(args):
  parser = argparse.ArgumentParser(
      description='Emulate one or more slave workers.')
  parser.add_argument('-u', '--url',  default='http://localhost:8080',
                      help='url of scheduler')
  parser.add_argument('-j', '--slaves', default=1, metavar='N', type=int,
                      help='number of slaves to emulate')
  parser.add_argument('-f', '--fanout', default=5, metavar='N', type=int,
                      help='fanout / width of dependency tree')
  parser.add_argument('-d', '--depth', default=5, metavar='N', type=int,
                      help='depth of dependency tree')
  parser.add_argument('-e', '--edges', default=0.3, type=float,
                      help='chance of each edge in dependency tree')
  parser.add_argument('-t', '--timeout', default=5, metavar='S', type=int,
                      help='how long (in seconds) to let slaves run')
  loglevel = parser.add_mutually_exclusive_group()
  loglevel.add_argument('-v', '--verbose', action='store_const', const='DEBUG',
                        dest='loglevel', default='INFO')
  loglevel.add_argument('-q', '--quiet', action='store_const', const='ERROR',
                        dest='loglevel', default='INFO')
  return parser.parse_args(args)


def main(args):
  opts = parse_args(args)
  LOGGER.setLevel(opts.loglevel)

  graph, roots = gen_deps(opts.fanout, opts.depth, opts.edges)
  post_jobs(opts.url, roots)

  children = []
  for _ in xrange(opts.slaves):
    c = Process(target=fake_slave, args=(opts.url, graph))
    children.append(c)
    LOGGER.debug('Starting child %s.', c.name)
    c.start()
  for c in children:
    c.join()
    LOGGER.debug('Joining child %s.', c.name)


if __name__ == '__main__':
  logging.basicConfig()
  sys.exit(main(sys.argv[1:]))