# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import jinja2
import json
import os
import webapp2

from google.appengine.ext import ndb

import models


JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.join(os.path.dirname(__file__),
                                                'templates')),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)


class AlertsHandler(webapp2.RequestHandler):

  @staticmethod
  def get_tree_status_dict(project):
    stat = models.TreeOpenStat.query(
        models.TreeOpenStat.num_days == 7, ancestor=project).order(
            -models.TreeOpenStat.timestamp).get()
    return {
        'should_alert': stat.percent_open > 80.0,
        'details': ('Tree %.2f%% open over last 7 days (must be > 80.0)' %
                    stat.percent_open),
        'url': ('http://trooper-o-matic.appspot.com/project/%s/tree-status' %
                project.id()),
    }

  @staticmethod
  def get_cq_latency_dict(project):
    stat = models.CqStat.query(ancestor=project).order(
        -models.CqStat.timestamp).get()
    return {
        'should_alert': stat.p50 < 60 and stat.p90 < 180,
        'details': ('CQ latency is median %dm and 90th %dm '
                    '(must be less than median 60m and 90th 180m' % (
                        stat.p50, stat.p90)),
        'url': 'http://trooper-o-matic.appspot.com/cq/%s' % project.id(),
    }

  @staticmethod
  def get_cycle_time_dict(tree):
    stat = models.BuildTimeStat.query(ancestor=tree).order(
        -models.BuildTimeStat.timestamp).get()
    # TODO(sullivan): Make this account for clobber time.
    return {
        'should_alert': (stat.num_over_max_slo == 0 and
                         stat.num_over_median_slo < (stat.num_builds / 2)),
        'details': ('%d builds over maximum 60m, %d builds over median 30m' % (
            stat.num_over_max_slo, stat.num_over_median_slo)),
        'url': 'http://trooper-o-matic.appspot.com/tree/%s' % tree.id()
    }

  def update_json_for_project(self, name, status_dict):
    project = ndb.Key('Project', name)
    tree = ndb.Key('Tree', name)
    status_dict.setdefault('tree-status', {})[name] = self.get_tree_status_dict(
        project)
    status_dict.setdefault('cq-latency', {})[name] = self.get_cq_latency_dict(
        project)
    status_dict.setdefault('cycle-time', {})[name] = self.get_cycle_time_dict(
        tree)

  def get(self):
    status_dict = {}
    self.update_json_for_project('blink', status_dict)
    self.update_json_for_project('chromium', status_dict)
    self.response.write(json.dumps(status_dict))

