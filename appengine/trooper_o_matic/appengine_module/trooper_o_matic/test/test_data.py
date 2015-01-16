# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import calendar
import datetime
import json

def _CreateTimestamp(hr, minute):
  return calendar.timegm(datetime.datetime(2014, 1, 1, hr, minute).timetuple())


CQ_API_RESPONSE1 = {
    'cursor': 'some-cursor',
    'results': [
      {
        'timestamp': _CreateTimestamp(11, 59),
        'fields': {
            'project': 'blink',
            'action': 'patch_stop',
            'issue': 12345,
            'patchset': 2001,
        },
      },
      {
        'timestamp': _CreateTimestamp(11, 50),
        'fields': {
            'project': 'chromium',
            'action': 'patch_stop',
            'issue': 54321,
            'patchset': 1,
        },
      },
      {
        'timestamp': _CreateTimestamp(11, 15),
        'fields': {
            'project': 'blink',
            'action': 'patch_stop',
            'issue': 987654,
            'patchset': 2001,
        },
      },
    ],
    'more': True,
}


CQ_API_RESPONSE2 = {
    'cursor': 'dead-end',
    'results': [
      {
        'timestamp': _CreateTimestamp(11, 30),
        'fields': {
            'project': 'chromium',
            'action': 'patch_stop',
            'issue': 54321,
            'patchset': 1,
        },
      },
      {
        'timestamp': _CreateTimestamp(11, 27),
        'fields': {
            'project': 'blink',
            'action': 'patch_stop',
            'issue': 12345,
            'patchset': 2001,
        },
      },
      {
        'timestamp': _CreateTimestamp(11, 1),
        'fields': {
            'project': 'chromium',
            'action': 'patch_stop',
            'issue': 499494,
            'patchset': 2001,
        },
      },
    ],
    'more': False,
}


CQ_PATCHSET_RESPONSES = [
    {
        # blink 12345 2001
        'results': [
        {
            # Ignored, patch start not finished yet
            'fields': {
                'timestamp': _CreateTimestamp(12, 0),
                'action': 'patch_start',
            },
        }, {
            'fields': {
                'timestamp': _CreateTimestamp(11, 59),
                'action': 'patch_stop',  # 29 minutes
            },
        }, {
            'fields': {
                'timestamp': _CreateTimestamp(11, 30),
                'action': 'patch_start',
            },
        }, {
            'fields': {
                'timestamp': _CreateTimestamp(11, 27),
                'action': 'patch_stop',  # 27 minutes
            },
        }, {
            'fields': {
                'timestamp': _CreateTimestamp(11, 0),
                'action': 'patch_start',
            },
        }]
    }, {
        # blink 987654, 2001
        'results': [{
            'fields': {
                'timestamp': _CreateTimestamp(11, 15),
                'action': 'patch_stop',  # 45 minutes
            },
        }, {
            'fields': {
                'timestamp': _CreateTimestamp(10, 30),
                'action': 'patch_start',
            },
        }]
    }, {
        # chromium 54321, 1
        'results': [{
            'fields': {
                'timestamp': _CreateTimestamp(11, 50),
                'action': 'patch_stop',  # ignored, not valid
            },
        }, {
            'fields': {
                'timestamp': _CreateTimestamp(11, 30),
                'action': 'patch_stop',  # 20 minutes
            },
        }, {
            'fields': {
                'timestamp': _CreateTimestamp(11, 10),
                'action': 'patch_start',
            },
        },]
    }, {
        # chromium 499494
        'results': [{
            'fields': {
                'timestamp': _CreateTimestamp(11, 1),
                'action': 'patch_stop',  # 61 minutes
            },
        },{
            'fields': {
                'timestamp': _CreateTimestamp(10, 0),
                'action': 'patch_start',
            },
        },{
            'fields': {
                'timestamp': _CreateTimestamp(9, 59),
                'action': 'patch_start',  # ignored, not valid
            },
        },]
    }
]


CQ_BLINK_HOURLY_FALSE_REJECTION_RESPONSE = {
    'results': [
        {
            'begin': 1421373600.0,
            'end': 1421377200.0,
            'interval_minutes': 60,
            'key': 4910980345626624,
            'project': 'blink',
            'stats': [
                {
                    'count': 0,
                    'description': ('Number of patchsets rejected by the '
                                    'trybots that eventually passed.'),
                    'name': 'patchset-false-reject-count',
                    'type': 'count'
                },
                {
                    'count': 3,
                    'description': 'Number of CQ attempts made.',
                    'name': 'attempt-count',
                    'type': 'count'
                }
            ]
        }
    ]
}


CQ_BLINK_WEEKLY_FALSE_REJECTION_RESPONSE = {
    'results': [
        {
            'begin': 1420444800.0,
            'end': 1421049600.0,
            'interval_minutes': 10080,
            'key': 6288129061289984,
            'project': 'blink',
            'stats': [
                {
                    'count': 158,
                    'description': ('Number of patchsets rejected by the '
                                    'trybots that eventually passed.'),
                    'name': 'patchset-false-reject-count',
                    'type': 'count'
                },
                {
                    'count': 608,
                    'description': 'Number of CQ attempts made.',
                    'name': 'attempt-count',
                    'type': 'count'
                }
            ]
        }
    ]
}



CQ_CHROMIUM_HOURLY_FALSE_REJECTION_RESPONSE = {
    'results': [
        {
            'begin': 1421373600.0,
            'end': 1421377200.0,
            'interval_minutes': 60,
            'key': 5073502444978176,
            'project': 'chromium',
            'stats': [
                {
                    'count': 3,
                    'description': ('Number of patchsets rejected by the '
                                    'trybots that eventually passed.'),
                    'name': 'patchset-false-reject-count',
                    'type': 'count'
                },
                {
                    'count': 15,
                    'description': 'Number of CQ attempts made.',
                    'name': 'attempt-count',
                    'type': 'count'
                }
            ]
        }
    ]
}


CQ_CHROMIUM_WEEKLY_FALSE_REJECTION_RESPONSE = {
    'results': [
        {
            'begin': 1420444800.0,
            'end': 1421049600.0,
            'interval_minutes': 10080,
            'key': 5665442689449984,
            'project': 'chromium',
            'stats': [
                {
                    'count': 346,
                    'description': ('Number of patchsets rejected by the '
                                    'trybots that eventually passed.'),
                    'name': 'patchset-false-reject-count',
                    'type': 'count'
                },
                {
                    'count': 1678,
                    'description': 'Number of CQ attempts made.',
                    'name': 'attempt-count',
                    'type': 'count'
                }
            ]
        }
    ]
}


CHROMIUM_MASTER_TREE = {
    'step_records': [{
        # Ignored -- generated too long ago
        'generated': '2014-01-01T10:00:00.000000',
        'step_time': 3500,
        'builder': 'Android',
        'buildnumber': 2500,
        'result': 0,
        'revision': '12345',
    }, {
        # Under SLO
        'generated': '2014-01-01T11:59:00.000000',
        'step_time': 100,
        'builder': 'Windows',
        'buildnumber': 1500,
        'result': 1,
        'revision': '12343',
    }, {
        # Over median, under max SLO
        'generated': '2014-01-01T11:50:00.000000',
        'step_time': 5500,
        'builder': 'Linux',
        'buildnumber': 500,
        'result': 0,
        'revision': '12245',
    }, {
        # Over max SLO
        'generated': '2014-01-01T12:00:00.000000',
        'step_time': 28900,
        'builder': 'Android',
        'buildnumber': 2500,
        'result': 0,
        'revision': '12345',
    },],
}


CHROMIUM_WIN_MASTER_TREE = {
    'step_records': [{
        # Ignored -- generated too long ago
        'generated': '2014-01-01T08:00:00.000000',
        'step_time': 2200,
        'builder': 'Win XP',
        'buildnumber': 500,
        'result': 0,
        'revision': '1245',
    }, {
        # Over median, under max SLO
        'generated': '2014-01-01T12:00:00.000000',
        'step_time': 5500,
        'builder': 'Windows 8',
        'buildnumber': 5500,
        'result': 1,
        'revision': '12243',
    },],
}


CHROMIUM_WIN_MASTER_TREE_24H = {
    'step_records': [{
        # Over median, under max SLO
        'generated': '2014-01-01T11:59:00.0000',
        'step_time': 5500,
        'builder': 'Windows 7',
        'buildnumber': 55,
        'result': 0,
        'revision': '32a5653f715e45901798ae3635db1339bed4fd7d',
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
    ('http://chromium-cq-status.appspot.com/query/action=patch_stop/?'
     'begin=1388574000'): {
        'statuscode': 200,
        'content': json.dumps(CQ_API_RESPONSE1)
    },
    ('http://chromium-cq-status.appspot.com/query/action=patch_stop/?'
     'begin=1388574000&cursor=some-cursor'): {
        'statuscode': 200,
        'content': json.dumps(CQ_API_RESPONSE2)
    },
    ('https://chromium-cq-status.appspot.com/query/'
     'issue=12345/patchset=2001/'): {
        'statuscode': 200,
        'content': json.dumps(CQ_PATCHSET_RESPONSES[0])
    },
    ('https://chromium-cq-status.appspot.com/query/'
     'issue=987654/patchset=2001/'): {
        'statuscode': 200,
        'content': json.dumps(CQ_PATCHSET_RESPONSES[1])
    },
    ('https://chromium-cq-status.appspot.com/query/'
     'issue=54321/patchset=1/'): {
        'statuscode': 200,
        'content': json.dumps(CQ_PATCHSET_RESPONSES[2])
    },
    ('https://chromium-cq-status.appspot.com/query/'
     'issue=499494/patchset=2001/'): {
        'statuscode': 200,
        'content': json.dumps(CQ_PATCHSET_RESPONSES[3])
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
     },
    ('https://chromium-cq-status.appspot.com/stats/query?project=blink&'
     'names=patchset-false-reject-count,attempt-count&interval_minutes=60&'
     'count=1'): {
         'statuscode': 200,
         'content': json.dumps(CQ_BLINK_HOURLY_FALSE_REJECTION_RESPONSE),
     },
    ('https://chromium-cq-status.appspot.com/stats/query?project=blink&'
     'names=patchset-false-reject-count,attempt-count&interval_minutes=10080&'
     'count=1'): {
         'statuscode': 200,
         'content': json.dumps(CQ_BLINK_WEEKLY_FALSE_REJECTION_RESPONSE),
     },
    ('https://chromium-cq-status.appspot.com/stats/query?project=chromium&'
     'names=patchset-false-reject-count,attempt-count&interval_minutes=60&'
     'count=1'): {
         'statuscode': 200,
         'content': json.dumps(CQ_CHROMIUM_HOURLY_FALSE_REJECTION_RESPONSE),
     },
    ('https://chromium-cq-status.appspot.com/stats/query?project=chromium&'
     'names=patchset-false-reject-count,attempt-count&interval_minutes=10080&'
     'count=1'): {
         'statuscode': 200,
         'content': json.dumps(CQ_CHROMIUM_WEEKLY_FALSE_REJECTION_RESPONSE),
     },
}
