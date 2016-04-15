# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import os
import subprocess
import sys
import time

from apiclient.errors import HttpError

import infra.services.bugdroid.poller_handlers as poller_handlers
import infra.services.bugdroid.svn_helper as svn_helper
from infra.services.bugdroid.poll import Poller


class HaltProcessing(Exception):
    def __init__(self):
        Exception.__init__(self)


class SVNPoller(Poller):

    def __init__(self, svn_url, poller_id, min_rev=0,
                 interval_in_minutes=3, setup_refresh_interval_minutes=0,
                 logger=None, run_once=False, datadir=None):
      Poller.__init__(self, interval_in_minutes,
                      setup_refresh_interval_minutes, run_once)

      self.svn_url = svn_url
      self.poller_id = poller_id
      self.filename = os.path.join(datadir or '', '%s.json' % self.poller_id)
      self.min_rev = min_rev
      self.last_rev = 1
      self.loaded = False
      self.__meta_data = {}
      self.handlers = []
      self.logger = logger
      self.loaded = False
      self._poll_failures = 0

      self.__load_meta_data()

    def __load_meta_data(self):
      if os.path.exists(self.filename):
        fp = open(self.filename, 'r')
        tmp = json.load(fp=fp)
        fp.close()
        if tmp:
          self.__meta_data = tmp

      if not self.__meta_data or 'last_rev' not in self.__meta_data:
        self.__meta_data['last_rev'] = 1
        self.__save_meta_data()

      self.last_rev = self.__meta_data['last_rev']
      self.loaded = True

      if self.min_rev > self.last_rev:
        self.last_rev = self.min_rev

    def __save_meta_data(self):
      fp = open(self.filename, 'w')
      json.dump(self.__meta_data, fp)
      fp.close()

    def __setattr__(self, key, value):
      self.__dict__[key] = value

      if ('loaded' in self.__dict__ and self.__dict__['loaded']
          and key in ['last_rev']):
        if self.__meta_data['last_rev'] != value:
          self.__meta_data['last_rev'] = value
          self.__save_meta_data()

    def __warm_up_handlers(self):
      for handler in self.handlers:
        handler.WarmUp()

    def __process_svn_log_entry(self, svn_log):
      for handler in self.handlers:
        try:
          handler.ProcessLogEntry(svn_log)
        except HaltProcessing:
          if self.logger:
            self.logger.exception('Uncaught exception 3 - Continuing')
          raise HaltProcessing
        except HttpError as e:
          #Log it here so that we see where it's breaking
          if self.logger:
            self.logger.exception('RequestError - Issue Tracker is Sad')
            #Let this error bubble up to we can handle the status code
          raise e
        except Exception as e :
          if self.logger:
            self.logger.exception('Uncaught exception 2 - Continuing')

    def add_handler(self, handler):
      if isinstance(handler, poller_handlers.BasePollerHandler):
        self.handlers.append(handler)
        handler.logger = self.logger

    def execute(self):
      try:
        entries = svn_helper.get_svn_log_entries(self.svn_url,
                                                 min_rev=self.last_rev,
                                                 limit=100)
      except subprocess.CalledProcessError as e:
        self._poll_failures += 1
        if self._poll_failures < 10:
          if self.logger:
            self.logger.exception(
              'Caught SVN exception (%s). Skipping polling.',
              self._poll_failures)
          return
        raise e
      self._poll_failures = 0

      self.__warm_up_handlers()

      for svn_log_entry in entries:
        #Prevent double processing
        if svn_log_entry.revision == self.last_rev:
          continue

        try:
          self.__process_svn_log_entry(svn_log_entry)
        except HttpError as e:
          if hasattr(e, 'resp') and hasattr(e.resp, 'status'):
            if e.resp.status in [403]:
              time.sleep(10)
            elif e.resp.status in [404]:
              self.logger.exception('Issue does not exist')
            elif e.resp.status in [500, 503]:
              self.logger.exception('Likely in read only mode')
              if not self.run_once:
                time.sleep(600)
              break

        except HaltProcessing:
          if self.logger:
            self.logger.exception('HaltProcessing - Terminating program')
            sys.exit(1)
        except Exception:
          if self.logger:
            self.logger.exception('Uncaught exception - Continuing')

        #If we get this far (i.e. haven't broken out of the loop),
        #increment the revision and move on.
        self.last_rev = svn_log_entry.revision
























