# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit tests for cron handlers.

This test requires the WebTest module. To install:
sudo apt-get install python-pip
sudo pip install WebTest
"""
import datetime
import json
import unittest
import webapp2
import webtest

from google.appengine.ext import testbed

from appengine.trooper_o_matic import cron
from appengine.trooper_o_matic import models
from appengine.trooper_o_matic.tests import testing_common

RIETVELD_RESPONSE = {
    'results': [{
        'project': 'chromium',
        'issue': '34562',
        'messages': [{
            # Ignore too old date
            'sender': 'commit-bot@chromium.org',
            'text': 'CQ is trying da patch. /author/12345/12',
            'date': '2014-01-01 01:59:00.123456'
        }, {
            'sender': 'commit-bot@chromium.org',
            'text': 'Change committed as 12345',
            'date': '2014-01-01 02:10:00.123456'
        }, {
            # Ignore invalid sender
            'sender': 'notcommitqueue@google.com',
            'text': 'CQ is trying da patch. /author/12345/12',
            'date': '2014-01-01 11:59:00.123456'
        }, {
            'sender': 'notcommitqueue@google.com',
            'text': 'Change committed as 12345',
            'date': '2014-01-01 12:10:00.123456'
        },],
    }, {
        # Ignore invalid project
        'project': 'something else',
        'issue': 'ignore',
        'messages': [{
            # Ignore too old date
            'sender': 'commit-bot@chromium.org',
            'text': 'CQ is trying da patch. /author/12345/12',
            'date': '2014-01-01 11:59:00.123456'
        }, {
            'sender': 'commit-bot@chromium.org',
            'text': 'Change committed as 12345',
            'date': '2014-01-01 12:10:00.123456'
        },]
    }, {
        # These should be added to 'blink' stats.
        'project': 'blink',
        'issue': '12345',
        # Ignored--user cancelled
        'messages': [{
            'sender': 'commit-bot@chromium.org',
            'text': 'CQ is trying da patch. /author/12345/2',
            'date': '2014-01-01 11:45:00.000000',
        }, {
            'sender': 'commit-bot@chromium.org',
            'text': 'CQ is trying da patch. /author/12345/2',
            'date': '2014-01-01 11:50:00.000000',
        }, {
            'sender': 'commit-bot@chromium.org',
            'text': 'List of reviewers changed.',
            'date': '2014-01-01 11:55:00.000000',  # 5 minutes
        }, {
            'sender': 'commit-bot@chromium.org',
            'text': 'CQ is trying da patch. /author/12345/2',
            'date': '2014-01-01 11:56:00.000000',
        }, {
            'sender': 'commit-bot@chromium.org',
            'text': 'Change committed as 45668',
            'date': '2014-01-01 11:59:00.000000',  # 3 minutes
        }],
    }, {
        # These should be added to 'chromium' stats.
        'project': 'chromium',
        'issue': '65435',
        # Ignored--user cancelled
        'messages': [{
            'sender': 'commit-bot@chromium.org',
            'text': 'CQ is trying da patch. /author/65435/2',
            'date': '2014-01-01 11:30:00.000000',
        }, {
            'sender': 'commit-bot@chromium.org',
            'text': 'Try jobs failed on following builders: foo',
            'date': '2014-01-01 11:47:00.000000',  # 17 minutes
        }, {
            'sender': 'commit-bot@chromium.org',
            'text': 'CQ is trying da patch. /author/65435/2',
            'date': '2014-01-01 11:49:00.000000',
        }, {
            'sender': 'commit-bot@chromium.org',
            'text': 'Commit queue failed due to new patchset.',
            'date': '2014-01-01 11:55:00.000000',  # 6 minutes
        }, {
            'sender': 'commit-bot@chromium.org',
            'text': 'CQ is trying da patch. /author/65435/4',
            'date': '2014-01-01 11:56:00.000000',
        }, {
            'sender': 'commit-bot@chromium.org',
            'text': 'Try jobs failed on following builders: foo',
            'date': '2014-01-01 12:01:00.000000',  # 5 minutes
        }],
    }, {
        # These should be added to 'chromium' stats.
        'project': 'chromium',
        'issue': '349205',
        # Ignored--user cancelled
        'messages': [{
            'sender': 'commit-bot@chromium.org',
            'text': 'CQ is trying da patch. /author/349205/2',
            'date': '2014-01-01 11:25:00.000000',
        }, {
            'sender': 'commit-bot@chromium.org',
            'text': 'Step "update" is always a major failure.',
            'date': '2014-01-01 11:47:00.000000',  # 22 minutes
        }, {
            'sender': 'commit-bot@chromium.org',
            'text': 'CQ is trying da patch. /author/349205/2',
            'date': '2014-01-01 11:48:00.000000',
        }, {
            'sender': 'commit-bot@chromium.org',
            'text': 'Failed to apply patch',
            'date': '2014-01-01 11:49:00.000000',  # 1 minute
        }, {
            'sender': 'commit-bot@chromium.org',
            'text': 'CQ is trying da patch. /author/349205/4',
            'date': '2014-01-01 11:50:00.000000',
        }, {
            'sender': 'commit-bot@chromium.org',
            'text': 'Try jobs failed on following builders: foo',
            'date': '2014-01-01 12:01:00.000000',  # 11 minutes
        }, {
            # Ignore since no finish
            'sender': 'commit-bot@chromium.org',
            'text': 'CQ is trying da patch. /author/349205/4',
            'date': '2014-01-01 12:02:00.000000',
        }],
    }],
}

CHROMIUM_MASTER_TREE = {
    'step_records': [{
        # Ignored -- generated too long ago
        'generated': '2014-01-01T10:00:00.000000',
        'step_time': 3500,
        'builder': 'Android',
        'buildnumber': 2500,
        'result': 0,
        'revision': 12345,
    }, {
        # Under SLO
        'generated': '2014-01-01T11:59:00.000000',
        'step_time': 100,
        'builder': 'Windows',
        'buildnumber': 1500,
        'result': 1,
        'revision': 12343,
    }, {
        # Over median, under max SLO
        'generated': '2014-01-01T11:50:00.000000',
        'step_time': 2000,
        'builder': 'Linux',
        'buildnumber': 500,
        'result': 0,
        'revision': 12245,
    }, {
        # Over max SLO
        'generated': '2014-01-01T12:00:00.000000',
        'step_time': 5500,
        'builder': 'Android',
        'buildnumber': 2500,
        'result': 0,
        'revision': 12345,
    },],
}

CHROMIUM_WIN_MASTER_TREE = {
    'step_records': [{
        # Ignored -- generated too long ago
        'generated': '2014-01-01T08:00:00.000000',
        'step_time': 5500,
        'builder': 'Win XP',
        'buildnumber': 500,
        'result': 0,
        'revision': 1245,
    }, {
        # Over median, under max SLO
        'generated': '2014-01-01T12:00:00.000000',
        'step_time': 2200,
        'builder': 'Windows 8',
        'buildnumber': 5500,
        'result': 1,
        'revision': 12243,
    },],
}

CHROMIUM_WIN_MASTER_TREE_24H = {
    'step_records': [{
        # Over median, under max SLO
        'generated': '2014-01-01T11:59:00.0000',
        'step_time': 1900,
        'builder': 'Windows 7',
        'buildnumber': 55,
        'result': 0,
        'revision': 12340,
    }]
}

CHROMIUM_TREE_DATA = [{
    'date': '2013-12-27 12:00:00.000000',
    'message': 'Tree is closed (details)',
    'can_commit_freely': False,
}, {
    'date': '2013-12-28 12:00:00.000000',
    'message': 'Tree is open (message)',
    'can_commit_freely': True,
}, {
    'date': '2013-12-24 00:00:00.000000',
    'message': 'Tree is closed (x)',
    'can_commit_freely': False,
}, {
    'date': '2013-12-25 12:00:00.000000',
    'message': 'Tree is open (blah)',
    'can_commit_freely': True,
}, {
    'date': '2013-12-28 13:00:00.000000',
    'message': 'Tree is closed for maintenance (message)',
    'can_commit_freely': False,
}, {
    'date': '2013-12-30 00:00:00.000000',
    'message': 'Tree is closed (blah)',
    'can_commit_freely': False,
}, {
    'date': '2013-12-30 12:00:00.000000',
    'message': 'Tree is open (details)',
    'can_commit_freely': True,
},]

URLFETCH_RESPONSES = {
    ('https://codereview.chromium.org/search?format=json&limit=500&'
     'with_messages=1&order=modified&'
     'modified_after=2014-01-01%2011%3A00%3A00'): {
         'statuscode': 200,
         'content': json.dumps(RIETVELD_RESPONSE)
     },
    'https://chromium-commit-queue.appspot.com/api/chromium/pending': {
        'statuscode': 200,
        'content': json.dumps({'results': [1, 2, 3, 4, 5]})
    },
    'https://chromium-commit-queue.appspot.com/api/blink/pending': {
        'statuscode': 200,
        'content': json.dumps({'results': [1, 2, 3]})
    },
    ('https://chromium.googlesource.com/chromium/tools/build/+'
     '/master/scripts/slave/gatekeeper_trees.json?format=text'): {
         'statuscode': 200,
         'content': ('eyJjaHJvbWl1bSI6IHsibWFzdGVycyI6IFsiaHR0cHM6Ly9idWlsZC5'
                     'jaHJvbWl1bS5vcmcvcC9jaHJvbWl1bSIsICJodHRwczovL2J1aWxkLmN'
                     'ocm9taXVtLm9yZy9wL2Nocm9taXVtLndpbiJdfX0='),
     },
    ('https://chrome-infra-stats.appspot.com/_ah/api/stats/v1/steps/chromium/'
     'overall__build__result__/2014-01-01T12:00Z'): {
         'statuscode': 200,
         'content': json.dumps(CHROMIUM_MASTER_TREE),
     },
    ('https://chrome-infra-stats.appspot.com/_ah/api/stats/v1/steps/'
     'chromium.win/overall__build__result__/2014-01-01T12:00Z'): {
         'statuscode': 200,
         'content': json.dumps(CHROMIUM_WIN_MASTER_TREE),
     },
    ('https://chrome-infra-stats.appspot.com/_ah/api/stats/v1/steps/'
     'chromium.win/overall__build__result__/2013-12-31T13:00Z'): {
         'statuscode': 200,
         'content': json.dumps(CHROMIUM_WIN_MASTER_TREE_24H),
     },
    ('https://chromium-status.appspot.com/allstatus?format=json&'
     'endTime=1387800000&limit=1000'): {
         'statuscode': 200,
         'content': json.dumps(CHROMIUM_TREE_DATA),
     },
    ('https://chromium-status.appspot.com/allstatus?format=json&'
     'endTime=1388318400&limit=1000'): {
         'statuscode': 200,
         'content': json.dumps(CHROMIUM_TREE_DATA),
     }
}


def MockNow():
  return datetime.datetime(2014, 1, 1, 12)

# Fill in empty data for all 24 hour periods not mocked out.
for hour in range(0, 24):
  for master in ['chromium', 'chromium.win']:
    h = (MockNow() - datetime.timedelta(hours=hour)).strftime('%Y-%m-%dT%H:%MZ')
    url = ('https://chrome-infra-stats.appspot.com/_ah/api/stats/v1/steps/%s/'
           'overall__build__result__/%s') % (master, h)
    if not URLFETCH_RESPONSES.get(url):
      URLFETCH_RESPONSES[url] = {
          'content': json.dumps({'step_records': []}),
          'statuscode': 200,
      }


class CronTest(unittest.TestCase):

  def setUp(self):

    self.testbed = testbed.Testbed()
    self.testbed.activate()
    self.testbed.init_datastore_v3_stub()
    self.testbed.init_memcache_stub()
    self.testbed.init_urlfetch_stub()
    testing_common.StubUrlfetch(URLFETCH_RESPONSES,
                                stub=self.testbed.get_stub('urlfetch'))
    app = webapp2.WSGIApplication([
        ('/check-cq', cron.CheckCqHandler),
        ('/check-tree/(.*)', cron.CheckTreeHandler),
        ('/check-tree-status/([^/]*)/(.*)', cron.CheckTreeStatusHandler),
    ])
    self.testapp = webtest.TestApp(app)
    cron.datetime_now = MockNow

  def testCheckCq(self):
    self.testapp.get('/check-cq')
    stats = models.CqStat.query().fetch()
    self.assertEqual(2, len(stats))
    self.assertEqual('blink', stats[0].key.parent().id())
    self.assertEqual(3, stats[0].length)
    self.assertEqual(3, stats[0].min)
    self.assertEqual(5, stats[0].max)
    self.assertEqual(4, stats[0].mean)
    self.assertEqual('chromium', stats[1].key.parent().id())
    self.assertEqual(5, stats[1].length)
    self.assertEqual(1, stats[1].min)
    self.assertEqual(22, stats[1].max)
    self.assertEqual(8.5, stats[1].p50)
    self.assertEqual(19.5, stats[1].p90)
    self.assertEqual(21.750000000000004, stats[1].p99)
    self.assertEqual(10.333333333333334, stats[1].mean)

  def testCheckTree(self):
    self.testapp.get('/check-tree/chromium')
    trees = models.Tree.query().fetch()
    self.assertEqual(1, len(trees))
    self.assertEqual('chromium', trees[0].key.id())
    stats = models.BuildTimeStat.query().fetch()
    self.assertEqual(1, len(stats))
    self.assertEqual(5, stats[0].num_builds)
    self.assertEqual(4, stats[0].num_over_median_slo)
    self.assertEqual(1, stats[0].num_over_max_slo)
    self.assertEqual(4, len(stats[0].slo_offenders))
    self.assertEqual('chromium', stats[0].slo_offenders[0].tree)
    self.assertEqual('chromium', stats[0].slo_offenders[1].tree)
    self.assertEqual('chromium', stats[0].slo_offenders[2].tree)
    self.assertEqual('chromium', stats[0].slo_offenders[0].master)
    self.assertEqual('chromium', stats[0].slo_offenders[1].master)
    self.assertEqual('chromium.win', stats[0].slo_offenders[2].master)
    self.assertEqual('Linux', stats[0].slo_offenders[0].builder)
    self.assertEqual('Android', stats[0].slo_offenders[1].builder)
    self.assertEqual('Windows 8', stats[0].slo_offenders[2].builder)
    self.assertEqual(500, stats[0].slo_offenders[0].buildnumber)
    self.assertEqual(2500, stats[0].slo_offenders[1].buildnumber)
    self.assertEqual(5500, stats[0].slo_offenders[2].buildnumber)
    self.assertEqual(2000, stats[0].slo_offenders[0].buildtime)
    self.assertEqual(5500, stats[0].slo_offenders[1].buildtime)
    self.assertEqual(2200, stats[0].slo_offenders[2].buildtime)
    self.assertEqual(0, stats[0].slo_offenders[0].result)
    self.assertEqual(0, stats[0].slo_offenders[1].result)
    self.assertEqual(1, stats[0].slo_offenders[2].result)
    self.assertEqual(1800, stats[0].slo_offenders[0].slo_median_buildtime)
    self.assertEqual(3600, stats[0].slo_offenders[0].slo_max_buildtime)

  def testCheckTreeStatusSevenDays(self):
    self.testapp.get('/check-tree-status/chromium/7')
    projects = models.Project.query().fetch()
    self.assertEqual(len(projects), 1)
    self.assertEqual('chromium', projects[0].key.id())
    stats = models.TreeOpenStat.query().fetch()
    self.assertEqual(1, len(stats))
    self.assertEqual(7, stats[0].num_days)
    self.assertEqual(78.57142857142857, stats[0].percent_open)

  def testCheckTreeStatusOneDayNoChanges(self):
    self.testapp.get('/check-tree-status/chromium/1')
    projects = models.Project.query().fetch()
    self.assertEqual(1, len(projects))
    self.assertEqual('chromium', projects[0].key.id())
    stats = models.TreeOpenStat.query().fetch()
    self.assertEqual(1, len(stats))
    self.assertEqual(1, stats[0].num_days)
    self.assertEqual(100.0, stats[0].percent_open)


if __name__ == '__main__':
  unittest.main()
