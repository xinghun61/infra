# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import copy
import datetime
import json
import mock
import urllib
import webapp2

from testing_utils import testing

from handlers import step_by_step_comparison
from waterfall import buildbot


class StepByStepComparisonTest(testing.AppengineTestCase):
  app_module = webapp2.WSGIApplication(
      [
          ('/step_by_step', step_by_step_comparison.StepByStepComparison),
      ],
      debug=True)

  def testFlatten(self):
    build_info = {'step': {'substep': [{'step': {'name': 'fake_step'}}]}}
    self.assertEqual([{
        'name': 'fake_step'
    }], step_by_step_comparison._Flatten(build_info))

  @mock.patch.object(buildbot, 'GetBuildInfo')
  @mock.patch.object(step_by_step_comparison, '_Flatten')
  def testGetStepsForTryJob(self, mock_flatten, mock_info):
    with self.assertRaises(ValueError):
      step_by_step_comparison._GetStepsForTryJob('http://invalid.url/bad/path',
                                                 None)
    fake_data = {'fake': 'data'}
    fake_json = json.dumps(fake_data)
    mock_info.return_value = fake_json
    step_by_step_comparison._GetStepsForTryJob(
        'https://luci-milo.appspot.com/swarming/task/373733328e9e9d10', None)
    mock_flatten.assert_called_with(fake_data)

  def testFindByName(self):
    steps = [{'name': 'fake_step'}]
    self.assertEqual(steps[0],
                     step_by_step_comparison._FindByName('fake_step', steps))
    self.assertIsNone(step_by_step_comparison._FindByName('bogus_name', steps))

  def testArrangeStepsSideBySide(self):
    swarmbucket_steps = [
        {
            'name': 'prepare',
            'started': '2017-01-01T00:00:00.000000000Z',
            'ended': '2017-01-01T00:01:00.000000000Z',
        },
        {
            'name': 'execute',
            'started': '2017-01-01T00:01:00.000000000Z',
            'ended': '2017-01-01T00:02:00.000000000Z',
        },
        {
            'name': 'overhead',
            'started': '2017-01-01T00:02:00.000000000Z',
            'ended': '2017-01-01T00:03:00.000000000Z',
        },
        {
            'name': 'analyze',
            'started': '2017-01-01T00:03:00.000000000Z',
            'ended': '2017-01-01T00:05:00.000000000Z',
        },
        {
            'name': 'stray',
            'started': '2017-01-01T00:05:00.000000000Z',
            'ended': '2017-01-01T00:05:01.000000000Z',
        },
        {
            'name': 'report',
            'started': '2017-01-01T00:05:01.000000000Z',
            'ended': '2017-01-01T00:05:01.000000000Z',
        },
        {
            'name': 'swarming_only',
            'started': '2017-01-01T00:05:01.000000000Z',
            'ended': '2017-01-01T00:05:01.000000000Z',
        },
        {
            'name': 'swarming_only_2',
            'started': '2017-01-01T00:05:01.000000000Z',
            'ended': '2017-01-01T00:05:01.000000000Z',
        },
    ]
    buildbucket_steps = [
        {
            'name': 'buildbucket_only_step',
            'started': '2017-01-01T00:05:10.000000000Z',
            'ended': '2017-01-01T00:05:19.000000000Z',
        },
        {
            'name': 'prepare',
            'started': '2017-01-01T00:00:00.000000000Z',
            'ended': '2017-01-01T00:01:30.000000000Z',
        },
        {
            'name': 'stray',
            'started': '2017-01-01T00:01:30.000000000Z',
            'ended': '2017-01-01T00:01:32.000000000Z',
        },
        {
            'name': 'execute',
            'started': '2017-01-01T00:01:32.000000000Z',
            'ended': '2017-01-01T00:02:00.000000000Z',
        },
        {
            'name': 'new_overhead',
            'started': '2017-01-01T00:02:00.000000000Z',
            'ended': '2017-01-01T00:03:30.000000000Z',
        },
        {
            'name': 'analyze',
            'started': '2017-01-01T00:03:30.000000000Z',
            'ended': '2017-01-01T00:05:00.000000000Z',
        },
        {
            'name': 'new_report',
            'started': '2017-01-01T00:05:00.000000000Z',
            'ended': '2017-01-01T00:05:10.000000000Z',
        },
    ]

    # Rather than compare the whole data structure, simplify by casting each
    # step to bool. What we care about is that the side by side matches steps
    # that are common, and that it doesn't those that are not.
    expected = [  # yapf: disable
      [False, True, True, True,  True, True, True,  True,  True,  False, False],
      [True,  True, True, False, True, True, False, False, False, True,  True]
    ]
    result = step_by_step_comparison._ComparisonTable(
        copy.deepcopy(swarmbucket_steps),
        copy.deepcopy(buildbucket_steps)).ArrangeSteps()
    actual = [map(bool, x) for x in result]
    self.assertEqual(expected, actual)

    # Note that reversing the comparison does not yield an exact mirror result
    # because when two steps are common to both runs but are out of order, they
    # will be displayed in the order it appears on the left side. In this case,
    # it is the step called 'stray'.
    expected = [  # yapf: disable
      [True,  True, True, True, True,  False, True, True,  False, False, False],
      [False, True, True, True, False, True,  True, False, True,  True,  True]
    ]
    result = step_by_step_comparison._ComparisonTable(
        copy.deepcopy(buildbucket_steps),
        copy.deepcopy(swarmbucket_steps)).ArrangeSteps()
    actual = [map(bool, x) for x in result]
    self.assertEqual(expected, actual)

    # Make sure the order is not changed if nothing is passed on the right side.
    result = step_by_step_comparison._ComparisonTable(
        copy.deepcopy(buildbucket_steps), []).ArrangeSteps()

    self.assertEqual(buildbucket_steps, result[0])

    # And on the left.
    result = step_by_step_comparison._ComparisonTable(
        [], copy.deepcopy(buildbucket_steps)).ArrangeSteps()
    self.assertEqual(buildbucket_steps, result[1])

  def testParseTime(self):
    self.assertEqual(
        datetime.datetime(2017, 1, 2, 3, 4, 5, 6),
        step_by_step_comparison._ParseTime('2017-01-02T03:04:05.000006000Z'))

  def testComputeElapsedTime(self):
    self.assertEqual(60,
                     step_by_step_comparison._ComputeElapsedTime({
                         'name': 'prepare',
                         'started': '2017-01-01T00:00:00.000000000Z',
                         'ended': '2017-01-01T00:01:00.000000000Z',
                     }))
    self.assertFalse(
        step_by_step_comparison._ComputeElapsedTime({
            'name': 'prepare',
            'started': '2017-01-01T00:00:00.000000000Z',
        }))

  def testMakeRow(self):
    self.assertEqual(['prepare', 60.0, 'execute', 60.0, 0.0],
                     list(
                         step_by_step_comparison._MakeRow({
                             'name': 'prepare',
                             'started': '2017-01-01T00:00:00.000000000Z',
                             'ended': '2017-01-01T00:01:00.000000000Z',
                         }, {
                             'name': 'execute',
                             'started': '2017-01-01T00:01:00.000000000Z',
                             'ended': '2017-01-01T00:02:00.000000000Z',
                         })))

  @mock.patch.object(step_by_step_comparison, '_GetStepsForTryJob')
  def testGet(self, _mock_fn):
    with mock.patch.object(step_by_step_comparison._ComparisonTable,
                           'ArrangeSteps') as mock_arrange:
      url_a = 'https://luci-milo.appspot.com/swarming/task/373733328e9e9d10'
      url_b = ('https://luci-milo.appspot.com/buildbot/tryserver.chromium.linux'
               '/linux_chromium_variable/21998')
      query = urllib.urlencode({
          'swarmbucket_try_job': url_a,
          'buildbot_try_job': url_b
      })
      swarmbucket_steps = [
          {
              'name': 'prepare',
              'started': '2017-01-01T00:00:00.000000000Z',
              'ended': '2017-01-01T00:01:00.000000000Z',
          },
          {
              'name': 'execute',
              'started': '2017-01-01T00:01:00.000000000Z',
              'ended': '2017-01-01T00:02:00.000000000Z',
          },
          {
              'name': 'overhead',
              'started': '2017-01-01T00:02:00.000000000Z',
              'ended': '2017-01-01T00:03:00.000000000Z',
          },
          None,
          {
              'name': 'analyze',
              'started': '2017-01-01T00:03:00.000000000Z',
              'ended': '2017-01-01T00:05:00.000000000Z',
          },
          {
              'name': 'report',
              'started': '2017-01-01T00:05:00.000000000Z',
              'ended': '2017-01-01T00:05:01.000000000Z',
          },
          None,
      ]
      buildbucket_steps = [
          {
              'name': 'prepare',
              'started': '2017-01-01T00:00:00.000000000Z',
              'ended': '2017-01-01T00:01:30.000000000Z',
          },
          {
              'name': 'execute',
              'started': '2017-01-01T00:01:30.000000000Z',
              'ended': '2017-01-01T00:02:00.000000000Z',
          },
          None,
          {
              'name': 'new_overhead',
              'started': '2017-01-01T00:02:00.000000000Z',
              'ended': '2017-01-01T00:03:30.000000000Z',
          },
          {
              'name': 'analyze',
              'started': '2017-01-01T00:03:30.000000000Z',
              'ended': '2017-01-01T00:05:00.000000000Z',
          },
          None,
          {
              'name': 'new_report',
              'started': '2017-01-01T00:05:00.000000000Z',
              'ended': '2017-01-01T00:05:10.000000000Z',
          },
      ]
      mock_arrange.return_value = [swarmbucket_steps, buildbucket_steps]

      self.assertEqual(200,
                       self.test_app.get('/step_by_step?' + query).status_int)

  def testGetBadParams(self):
    url_a = 'https://luci-milo.appspot.com/swarming/task/373733328e9e9d10'
    query = urllib.urlencode({'swarmbucket_try_job': url_a})
    with self.assertRaisesRegexp(Exception, '.*400.*'):
      self.test_app.get('/step_by_step?' + query)

    url_a = 'https://luci-milo.appspot.com/swarming/task/373733328e9e9d10'
    url_b = ('https://luci-milo.appspot.com/buildbot/tryserver.chromium.linux'
             '/linux_chromium_variable/21998')
    query = urllib.urlencode({
        'swarmbucket_try_job': url_a,
        'buildbot_try_job': url_b
    })
    with mock.patch.object(buildbot, 'ValidateBuildUrl', return_value=False):
      with self.assertRaisesRegexp(Exception, '.*400.*'):
        self.test_app.get('/step_by_step?' + query)
