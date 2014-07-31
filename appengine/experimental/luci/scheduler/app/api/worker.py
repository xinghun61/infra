# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb

from app.framework.response import success, failure
from app.framework import Application
from app.api.model import Job, Worker, JobState


app = Application(auth_required=True, debug=True)


@ndb.transactional
def dequeue_job():
  """ Return oldest job which has all its dependencies satisfied. """
  jobs = Job.query(Job.state == JobState.QUEUED,
                   Job.num_deps == 0).order(Job.time_queued).fetch(1)
  if not len(jobs):
    return None

  jobs[0].state = JobState.STARTED
  jobs[0].put()
  return jobs[0]


@app.route('/api/v1/worker/<id>/heartbeat', methods=['POST'])
def heartbeat(request, id):
  worker = request.auth.require_entity(Worker)
  if worker.key.id() != id:
    return failure('Requested worker not authenticated')

  worker.put()
  return success({'worker' : worker})

@app.route('/api/v1/worker/<id>/acquire_job', methods=['POST'])
def acquire_job(request, id):
  worker = request.auth.require_entity(Worker)
  if worker.key.id() != id:
    return failure('Requested worker not authenticated')

  if worker.job is not None:
    return failure('Worker "%s" already owns job' % id)

  job = dequeue_job()
  if job is None:
    return failure('No job available')

  worker.job = job.key.id()
  worker.put()

  return success({'worker': worker, 'job': job})

@app.route('/api/v1/worker', methods=['GET'])
def get_all(request):
  limit = int(request.get('limit', 10))
  workers = model.Worker.query().fetch(limit)
  return success({'workers': workers})
