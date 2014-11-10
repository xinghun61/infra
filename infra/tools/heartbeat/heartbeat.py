# Copyright 2012 Google Inc. All Rights Reserved.

import base64
import datetime
import hashlib
import hmac
import json
import os
import random
import re
import socket
import string
import subprocess
import sys
import time

import requests


def get_name():
  """Get short hostname of the machine we're currently on."""
  return socket.gethostname().split('.', 1)[0]


def get_id():
  """Get or create an id for the machine."""
  id_file = os.path.expanduser('~/.heartbeat.id')
  if os.path.exists(id_file):
    with open(id_file, 'rb') as f:
      return f.read()

  # Create id and save to file.
  # id is of the format hostname-datestamp-random_word.
  hostname = get_name()
  # Just needs to be in the right ballpark.  Used to get an idea of when
  # the id was created.
  datestamp = datetime.date.today().isoformat()
  # Use dictionary words if available to make our IDs look less ugly.
  if os.path.exists('/usr/share/dict/words'):
    with open('/usr/share/dict/words') as f:
      word = random.choice(f.readlines())
    appendix = re.sub(r'\W+', '', word.lower())
  else:
    appendix = ''.join(random.choice(string.ascii_lowercase) for _ in range(6))
  uid = '%s-%s-%s' % (hostname, datestamp, appendix)
  with open(id_file, 'wb') as f:
    f.write(uid)
  return uid


def get_secret(secret_file):
  secret_file = os.path.expanduser(secret_file)
  if not os.path.exists(secret_file):
    secret = base64.urlsafe_b64encode(os.urandom(256))
    with os.fdopen(os.open(secret_file,
                           os.O_WRONLY | os.O_CREAT,
                           0600), 'wb') as f:
      f.write(secret)
    print 'No key found, generated key %s' % secret_file
  with open(secret_file, 'rb') as f:
    return f.read()


def get_heartbeat_data(name, uid):
  # Populate the data with name and dstat information.
  data = {
      'name': name or get_name(),
      'status': 0,
      'message': 'OK',
      'time': time.time(),
      'id': uid or get_id()
  }

  # Check to see if there are any more heartbeat scripts.
  # The format is check for are lines reading "key: value".
  current_dir = os.path.dirname(os.path.abspath(__file__))
  heartbeats_dir = os.path.join(current_dir, data['name'])
  if os.path.exists(heartbeats_dir):
    heartbeat_files = [os.path.join(heartbeats_dir, f)
        for f in os.listdir(heartbeats_dir)]
    heartbeat_files.sort()
    for filename in heartbeat_files:
      new_data = {}
      try:
        p = subprocess.Popen([filename], stdout=subprocess.PIPE)
      except OSError:
        new_data['message'] = 'FAIL - %s failed to run' % filename
        new_data['status'] = 1
        continue
      out, _ = p.communicate()
      for line in out.split('\n'):
        m = re.match(r'^([^:]+):\s*(.*)$', line)
        if m:
          k, v = m.groups()
          # Treat 'status' specially.
          if k == 'status':
            new_data['status'] = max(v, data['status'], new_data.get('status'))
          else:
            new_data[k] = v
      data.update(new_data)

  return data


def get_hashed_message(data, secret):
  """Hashes the message with the timestamp and the preshared key, and return
  a dict of the message, timestamp, and hash."""
  auth_method = 'HMAC-SHA256'
  message = json.dumps(data, separators=(',',':'))
  results = {
      'auth_method': auth_method,
      'message': message,
  }
  hasher = hmac.new(secret, digestmod=hashlib.sha256)
  hasher.update(auth_method)
  hasher.update(message)
  results['signature'] = hasher.hexdigest()
  return results


def send(message, urls):
  return_code = 0
  for url in urls:
    print 'Sending: %s to %s' % (str(message), url)
    try:
      r = requests.post(url, data=message, verify=True)
    except requests.HTTPError as e:
      print >> sys.stderr, 'Error: %s' % e
      return_code = max(e.code, return_code)
      continue

    # Check the status to see if we completed successfully.
    if r.status_code == 200:
      print 'Got code: %d.  OK' % r.status_code
    else:
      print >> sys.stderr, 'ERROR: Got code: %d' % r.status_code
      msg = r.content
      if msg:
        print >> sys.stderr, 'Got message: %s' % msg
      return_code = max(r.status_code, return_code)
  return return_code
