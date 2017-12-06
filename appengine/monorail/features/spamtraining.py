"""Cron job to train spam model with all spam data."""

import logging
import settings
import time

from googleapiclient import discovery
from googleapiclient import errors
from google.appengine.api import app_identity
from oauth2client.client import GoogleCredentials
import webapp2

class TrainSpamModelCron(webapp2.RequestHandler):

  """Submit a job to ML Engine which uploads a spam classification model by
     training on an already packaged trainer.
  """
  def get(self):

    credentials = GoogleCredentials.get_application_default()
    ml = discovery.build('ml', 'v1', credentials=credentials)

    app_id = app_identity.get_application_id()
    project_id = 'projects/%s' % (app_id)
    job_id = 'spam_training_%d' % time.time()
    training_input = {
        'scaleTier': 'BASIC',
        'packageUris': [
            settings.trainer_staging
            if app_id == "monorail-staging" else
            settings.trainer_prod
        ],
        'pythonModule': 'trainer.task',
        'args': [
            '--train-steps',
            '1000',
            '--verbosity',
            'DEBUG',
            '--gcs-bucket',
            'monorail-prod.appspot.com',
            '--gcs-prefix',
            'spam_training_data'
        ],
        'region': 'us-central1',
        'jobDir': 'gs://%s-mlengine/%s' % (app_id, job_id),
        'runtimeVersion': '1.2'
    }
    job_info = {
        'jobId': job_id,
        'trainingInput': training_input
    }
    request = ml.projects().jobs().create(parent=project_id, body=job_info)

    try:
      response = request.execute()
      logging.info(response)
    except errors.HttpError, err:
      logging.error(err._get_reason())
