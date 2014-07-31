# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import hashlib
from google.appengine.ext import ndb
from webapp2 import RequestHandler, WSGIApplication

from app.framework.response import success, failure, abort
from app.framework import Application
from app.api import model


app = Application(auth_required=True, debug=True)


@ndb.transactional
def add_deps(job, dep_ids):
  job_id = job.key.id()

  dep_count = 0
  for id in dep_ids:
    job = Job.get_by_id(id)
    if job.state == JobState.COMPLETED:
      continue
    elif job.state == JobState.FAILED:
      pass # TODO(nbharadwaj) create a new attempt

    if job_id not in job.reverse_deps:
      job.reverse_deps += job_id
      job.put()
      dep_count += 1

  job.num_deps += dep_count
  job.put()


@app.route('/api/v1/job', methods=['POST'])
def add_job(request):
  if ('name' not in request.body or
      'binary' not in request.body):
    return failure('Job body incomplete; name and binary fields required')
  name = request.body['name']
  binary = request.body['binary']
  params = request.body.get('param', [])

  id_prehash = str((
    ('binary', binary),
    ('params', tuple(params))
  ))
  m = hashlib.md5()
  m.update(id_prehash)
  id = m.hexdigest()

  job = model.Job(id=id)
  job.name = name
  job.binary = binary
  job.params = params
  job.put()
  return success({'job': job})

@app.route('/api/v1/job/<id>', methods=['DELETE'])
def delete_job(request, id):
  job = model.Job.get_by_id_or_abort(id).key.delete()
  return success()

@app.route('/api/v1/job', methods=['DELETE'])
def delete_all_jobs(request):
  job_keys = model.Job.query().fetch(keys_only=True)
  ndb.delete_multi(job_keys)
  return success()

@app.route('/api/v1/job/<id>', methods=['GET'])
def get_job(request, id):
  return success({'job': model.Job.get_by_id_or_abort(id)})

@app.route('/api/v1/job', methods=['GET'])
def get_all_jobs(request):
  # TODO(nbharadwaj) implement paging
  limit = int(request.get('limit', 10))
  return success({'jobs': model.Job.query().fetch(limit)})

@app.route('/api/v1/job/<id>', methods=['PUT'])
def update_job(request, id):
  job = Job.get_by_id_or_abort(id)
  worker = request.auth.require_entity(Worker)

  if job.worker != worker.key.id():
    return failure('Worker does not have write access to the job')
  if 'state' not in request.body:
    return failure('Updates to jobs must update the state')

  if request.body['state'] == JobState.QUEUED:
    return halt_job(request, worker, job)
  if request.body['state'] == JobState.COMPLETED:
    return complete_job(request, worker, job)
  if request.body['state'] == JobState.FAILED:
    return fail_job(request, worker, job)

def halt_job(request, worker, job):
  add_deps(job, request.body.get('deps', []))
  return success('worker': worker, 'job': job)

def complete_job(request, worker, job):
  job.result_hash = request.body.get('result_hash', None)
  job.log_path = request.body.get('log_path', None)
  job.state = JobState.COMPLETE
  job.put()

  worker.job = None
  worker.put()

  return success({'worker': worker, 'job': job})

def fail_job(request, worker, job):
  job.log_path = request.body.get('log_path', None)
  job.state = JobState.FAILED
  job.put()

  worker.job = None
  worker.put()

  return success({'worker': worker, 'job': job})
