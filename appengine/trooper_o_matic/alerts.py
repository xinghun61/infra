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


def GetTreeStatusDict(project): # pragma: no cover
  stat = models.TreeOpenStat.query(
      models.TreeOpenStat.num_days == 7, ancestor=project).order(
          -models.TreeOpenStat.timestamp).get()
  return {
      'should_alert': stat.percent_open < 80.0,
      'percent_open': stat.percent_open,
      'details': ('Tree %.2f%% open over last 7 days (must be > 80.0)' %
                  stat.percent_open),
      'url': ('http://trooper-o-matic.appspot.com/tree-status/%s' %
              project.id()),
  }

def GetCqLatencyDict(project): # pragma: no cover
  stat = models.CqStat.query(ancestor=project).order(
      -models.CqStat.timestamp).get()
  if not stat.p50:
    return {
        'should_alert': False,
        'p50': None,
        'p90': None,
        'length': stat.length,
        'details': 'No CQ jobs in last hour',
        'url': 'http://trooper-o-matic.appspot.com/cq/%s' % project.id(),
    }
  return {
      'should_alert': stat.p50 > 60 or stat.p90 > 180,
      'p50': stat.p50,
      'p90': stat.p90,
      'length': stat.length,
      'details': ('CQ latency is median %dm and 90th %dm '
                  '(must be less than median 60m and 90th 180m' % (
                      stat.p50, stat.p90)),
      'url': 'http://trooper-o-matic.appspot.com/cq/%s' % project.id(),
  }

def _GetPercent(numerator, denominator): # pragma: no cover
  if denominator == 0:
    return "0%"
  else:
    return "%.2f%%" % (float(numerator) / float(denominator) * 100)

def GetCycleTimeDict(tree): # pragma: no cover
  stat = models.BuildTimeStat.query(ancestor=tree).order(
      -models.BuildTimeStat.timestamp).get()
  # TODO(sullivan): Make this account for clobber time.
  return {
      'should_alert': (stat.num_over_max_slo > 0 or
                       stat.num_over_median_slo > (stat.num_builds / 2)),
      'num_builds': stat.num_builds,
      'num_over_median_slo': stat.num_over_median_slo,
      'percent_over_median_slo': _GetPercent(stat.num_over_median_slo,
                                             stat.num_builds),
      'num_over_max_slo': stat.num_over_max_slo,
      'percent_over_max_slo': _GetPercent(stat.num_over_max_slo,
                                          stat.num_builds),
      'details': ('%d builds over maximum 60m, %d builds over median 30m' % (
          stat.num_over_max_slo, stat.num_over_median_slo)),
      'url': 'http://trooper-o-matic.appspot.com/tree/%s' % tree.id()
  }

def UpdateJsonForProject(name, status_dict): # pragma: no cover
  project = ndb.Key('Project', name)
  tree = ndb.Key('Tree', name)
  status_dict.setdefault('tree_status', {})[name] = GetTreeStatusDict(project)
  status_dict.setdefault('cq_latency', {})[name] = GetCqLatencyDict(project)
  status_dict.setdefault('cycle_time', {})[name] = GetCycleTimeDict(tree)


class AlertsHandler(webapp2.RequestHandler): # pragma: no cover

  def get(self):
    status_dict = {}
    UpdateJsonForProject('blink', status_dict)
    UpdateJsonForProject('chromium', status_dict)
    self.response.headers.add_header('Access-Control-Allow-Origin', '*')
    self.response.write(json.dumps(status_dict))


class OverviewHandler(webapp2.RequestHandler): # pragma: no cover

  def get(self):
    status_dict = {}
    UpdateJsonForProject('blink', status_dict)
    UpdateJsonForProject('chromium', status_dict)

    template = JINJA_ENVIRONMENT.get_template('overview.html')
    self.response.write(template.render(status_dict))
