# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Prediction service for Monorail.
"""

import logging
import sklearn
import pickle
import json
import tempfile
import threading
import numpy as np

from googleapiclient import discovery
from googleapiclient import http

from oauth2client.client import GoogleCredentials

from flask import Flask, request, render_template


# These parameters determine the location of the model files on GCS.
BUCKET = 'monorail-predict'
MODEL_TIME = 1473989566


app = Flask(__name__)


# This should be set to true once the models are loaded and we're ready
# to serve requests.
ready = False
index_map, vectorizer, tfidf_transformer, clf = None, None, None, None


@app.route('/')
def text_area():
    return render_template('comment.html')


@app.route('/_predict', methods=['POST'])
def predict():
  text = request.form['text']
  text = text.lower().strip()
  counts = vectorizer.transform([text])
  tfidf = tfidf_transformer.transform(counts)
  predictions = clf.predict(tfidf)[0]

  # Translate array of indices into acual list of components
  predictions_path = []
  for index in np.where(predictions)[0]:
    predictions_path.append(index_map[index])

  return json.dumps({'components': predictions_path})


# Used by GAE Custom Flexible Runtime
@app.route('/_log', methods=['GET'])
def log():
  # TODO: more detailed logging. For now we can just look at the
  # GET request parameters.
  return 'ok'


# Used by GAE Custom Flexible Runtime
@app.route('/_ah/start')
def start():
  return 'ok'


# Used by GAE Custom Flexible Runtime
@app.route('/_ah/stop')
def stop():
    return 'ok'


# Used by GAE Custom Flexible Runtime
@app.route('/_ah/health')
def health():
  if ready:
    return 'ok'
  else:
    return '', 503 # HTTP_503_SERVICE_UNAVAILABLE


# Used by GAE Custom Flexible Runtime
@app.route('/_ah/background')
def background():
  return 'ok'


# CORS support.
@app.after_request
def after_request(response):
  response.headers.add('Access-Control-Allow-Origin', '*')
  response.headers.add('Access-Control-Allow-Headers',
      'Content-Type,Authorization')
  response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE')
  return response


@app.errorhandler(500)
def server_error(e):
  # Log the error and stacktrace.
  logging.exception('An error occurred during a request: %s.', e)
  return 'An internal error occurred.', 500


def create_service():
  # Get the application default credentials. When running locally, these are
  # available after running `gcloud init`. When running on compute
  # engine, these are available from the environment.
  credentials = GoogleCredentials.get_application_default()

  # Construct the service object for interacting with the Cloud Storage API -
  # the 'storage' service, at version 'v1'.
  # You can browse other available api services and versions here:
  #     http://g.co/dev/api-client-library/python/apis/
  return discovery.build('storage', 'v1', credentials=credentials)


def get_object(bucket, filename, out_file):
  service = create_service()

  # Use get_media instead of get to get the actual contents of the object.
  # http://g.co/dev/resources/api-libraries/documentation/storage/v1/python/latest/storage_v1.objects.html#get_media
  req = service.objects().get_media(bucket=bucket, object=filename)

  downloader = http.MediaIoBaseDownload(out_file, req,
     chunksize=100*1024*1024)

  done = False
  while done is False:
    status, done = downloader.next_chunk()
    print("Download {}%.".format(int(status.progress() * 100)))

  return out_file


def get_model(bucket, filename):
  print(filename)
  print('Fetching object..')
  # TODO: retries on errors. GCS doesn't always work.
  with tempfile.NamedTemporaryFile(mode='w+b') as tmpfile:
    get_object(bucket, filename, out_file=tmpfile)
    tmpfile.seek(0)

    model = pickle.load(tmpfile)

  return model


@app.before_first_request
def load_data():
  global ready, index_map, vectorizer, tfidf_transformer, clf
  index_map = get_model(BUCKET, 'model/{}-index-map.pkl'.format(MODEL_TIME))
  vectorizer = get_model(BUCKET, 'model/{}-vectorizer.pkl'.format(MODEL_TIME))
  tfidf_transformer = get_model(BUCKET,
                                  'model/{}-transformer.pkl'.format(MODEL_TIME))
  clf = get_model(BUCKET, 'model/{}-classifier.pkl'.format(MODEL_TIME))
  ready = True


loading_thread = threading.Thread(target=load_data)


if __name__ == '__main__':
  # Start loading model data, but also start serving right away so we
  # can respond to _ah/health requests with 503s rather than appearing to
  # not have started at all.
  loading_thread.start()
  app.run(host='0.0.0.0:8080')

