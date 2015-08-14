# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import json
import mock
import os
import re
import requests
import sqlite3
import unittest

import infra_libs
import infra.tools.antibody.cloudsql_connect as csql
from infra.tools.antibody import code_review_parse


class fake_requests_rietveld():
  @staticmethod
  def get(url):  # pragma: no cover
    assert url in [
        'https://codereview.chromium.org/api/1158153006?messages=true',
        'https://codereview.chromium.org/api/1175993003?messages=true',
        'https://codereview.chromium.org/api/1146053009?messages=true',
        'https://codereview.chromium.org/api/1004453003?messages=true',
        'https://codereview.chromium.org/api/1171763002?messages=true',
        'https://codereview.chromium.org/api/1175623002?messages=true',
        'https://codereview.chromium.org/api/1177013002?messages=true',
    ], 'URL conversion failed'
    return fake_response_rietveld(url)


class fake_response_rietveld():
  def __init__(self, url):  # pragma: no cover
    self.status_code = requests.codes.ok
    self.url = url

  def json(self):  # pragma: no cover
    prefix_len = len('https://codereview.chromium.org/api/')
    issue_len = len('1158153006')
    issue_num = self.url[prefix_len:prefix_len + issue_len]
    return json.load(open('infra/tools/antibody/test/data/%s.txt'
                          % issue_num, 'r'))


class fake_sql_lib():
  @staticmethod
  def write_to_review(cc, db_data):  # pragma: no cover
    # review_url, request_timestamp, committed_timestamp, patchset_still_exists
    # reverted, project_prj_id
    with open (os.path.join(cc.dirname(), 'output.txt'), 'a') as f:
      for x in xrange(len(db_data)):
        if x != 1:  # remove request_timestamp
          f.write("%s, " % db_data[x])
      f.write('\n')

  @staticmethod
  def write_to_review_people(cc, db_data):  # pragma: no cover
    # email_address, review_url, timestamp, request_timestamp, type
    with open (os.path.join(cc.dirname(), 'output.txt'), 'a') as f:
      for person in db_data:
        for x in xrange(len(person)):
          if x != 3:  # remove request_timestamp
            f.write("%s, " % person[x])
        f.write('\n')
      f.write('\n')


class fake_gerrit_util():
  @staticmethod
  def GetChangeDetail(_, change_id):
    if change_id:
      return json.load(open('infra/tools/antibody/test/data/%s.txt'
                          % change_id, 'r'))
    return None

@mock.patch('requests.get', side_effect=fake_requests_rietveld.get)
@mock.patch(
    'infra.tools.antibody.static.third_party.gerrit_util.GetChangeDetail',
    side_effect=fake_gerrit_util.GetChangeDetail)
def fake_extract_json_data(review_url, cc, checkout, _,
                           dummy):  # pragma: no cover
  if any(hostname in review_url for hostname in 
      code_review_parse.KNOWN_RIETVELD_INSTANCES):
    return code_review_parse._extract_json_data_from_rietveld(review_url)
  elif any(hostname in review_url for hostname in
      code_review_parse.KNOWN_GERRIT_INSTANCES):
    return code_review_parse._extract_json_data_from_gerrit(review_url, cc,
                                                            checkout)


class TestCodeReviewParse(unittest.TestCase):
  r_lgtm_no_tbr = 'https://codereview.chromium.org/1158153006'
  r_not_lgtm_no_tbr = 'https://codereview.chromium.org/1175993003'
  r_mult_lgtm_no_tbr = 'https://codereview.chromium.org/1146053009'
  r_no_lgtm_tbr = 'https://codereview.chromium.org/1004453003'
  r_no_lgtm_mult_tbr = 'https://codereview.chromium.org/1171763002'
  r_lgtm_tbr = 'https://codereview.chromium.org/1175623002'
  r_lgtm_not_lgtm_no_tbr = 'https://codereview.chromium.org/1177013002'

  g_not_lgtm = 'https://chromium-review.googlesource.com/288326'
  g_lgtm = 'https://chromium-review.googlesource.com/286215'
  g_committed = 'https://chromium-review.googlesource.com/285219'

  @mock.patch(
      'infra.tools.antibody.code_review_parse._extract_json_data_from_rietveld')
  @mock.patch(
      'infra.tools.antibody.code_review_parse._extract_json_data_from_gerrit')
  def test_extract_code_review_json_data(self, mock_g, mock_r):
    cc = None
    checkout = None
    code_review_parse.extract_code_review_json_data(self.r_lgtm_no_tbr, cc,
        checkout)
    mock_r.assert_called_with(self.r_lgtm_no_tbr)
    code_review_parse.extract_code_review_json_data(self.g_not_lgtm, cc,
        checkout)
    mock_g.assert_called_with(self.g_not_lgtm, cc, checkout)
    code_review_parse.extract_code_review_json_data('invalid url', cc,
        checkout)


  def test_extract_json_data_from_rietveld(self):
    _ = code_review_parse._extract_json_data_from_rietveld(
        self.r_lgtm_no_tbr)

  @mock.patch('subprocess.check_output', 
      side_effect=('x\nChange-Id: 288240', 'no change id', 
                   'Change-Id: 288240\nChange-Id: 288240'))
  @mock.patch(
      'infra.tools.antibody.static.third_party.gerrit_util.GetChangeDetail',
      side_effect=fake_gerrit_util.GetChangeDetail)
  def test_extract_json_data_from_gerrit(self, mock_gerrit_util, _):
    mock_cc = mock.MagicMock()
    checkout = None
    _ = code_review_parse._extract_json_data_from_gerrit(
        self.g_not_lgtm, mock_cc, checkout)
    mock_gerrit_util.assert_called_with(
        'chromium-review.googlesource.com', '288240')

    _ = code_review_parse._extract_json_data_from_gerrit(
        self.g_committed, mock_cc, checkout)
    mock_gerrit_util.assert_called_with(
        'chromium-review.googlesource.com', None)

    _ = code_review_parse._extract_json_data_from_gerrit(
        self.g_not_lgtm, mock_cc, checkout)
    mock_gerrit_util.assert_called_with(
        'chromium-review.googlesource.com', '288240')


  def test_to_canonical_review_url(self):
    chrome_internal_url = 'https://chromereviews.googleplex.com/210457013/'
    self.assertEqual(chrome_internal_url,
          code_review_parse.to_canonical_review_url(chrome_internal_url))

    cr_appspot_url = 'https://codereview.appspot.com/244460044/'
    self.assertEqual(cr_appspot_url,
                    code_review_parse.to_canonical_review_url(cr_appspot_url))

    chromiumcr_url = 'https://chromiumcodereview.appspot.com/1147143006/'
    self.assertEqual('https://codereview.chromium.org/1147143006/',
                    code_review_parse.to_canonical_review_url(chromiumcr_url))

    chromiumcr_hr_url = 'https://chromiumcodereview-hr.appspot.com/1147143006/'
    self.assertEqual('https://codereview.chromium.org/1147143006/',
                 code_review_parse.to_canonical_review_url(chromiumcr_hr_url))

    codereview_chromium_url = 'https://codereview.chromium.org/1147143006/'
    self.assertEqual(codereview_chromium_url,
           code_review_parse.to_canonical_review_url(codereview_chromium_url))


  @mock.patch(
      'infra.tools.antibody.code_review_parse.extract_code_review_json_data',
      side_effect=fake_extract_json_data)
  @mock.patch('subprocess.check_output',
      side_effect=('Change-Id: 287501',
                   'Change-Id: I2214717448776b5d2a60182a8e572f0b8d580561'))
  @mock.patch(
      'infra.tools.antibody.code_review_parse.get_urls_from_git_commit',
      return_value=(g_not_lgtm, r_lgtm_not_lgtm_no_tbr, g_lgtm,
                   r_lgtm_no_tbr, r_lgtm_tbr, 'fake url'))
  @mock.patch('infra.tools.antibody.cloudsql_connect.write_to_sql_table',
      side_effect=[fake_sql_lib.write_to_review,
                   fake_sql_lib.write_to_review_people])
  def DEACTIVATEtest_add_code_review_data_to_db(self, _,
      dummy):  # pragma: no cover
    mock_cc = mock.MagicMock()
    checkout = None
    with infra_libs.temporary_directory(prefix='antibody-test') as dirname:
      mock_cc.dirname.return_value = dirname
      code_review_parse.get_code_review_data(mock_cc, checkout)
      code_review_parse.get_code_review_data(mock_cc, checkout)
      code_review_parse.get_code_review_data(mock_cc, checkout)
      code_review_parse.get_code_review_data(mock_cc, checkout)
      code_review_parse.get_code_review_data(mock_cc, checkout)
      code_review_parse.get_code_review_data(mock_cc, checkout)
      with open (os.path.join(dirname, 'output.txt'), 'r') as f:
        return f.readlines()


  def test_get_tbr_no_lgtm(self):
    mock_cc = mock.MagicMock()
    mock_cc.fetchall.return_value = (
      ('https://codereview.chromium.org/993263002',
       datetime.datetime(2015, 03, 11, 07, 11, 54),
       'Reland-Changes-in-infra-to-get-bot_setup-to-work-on-GCE-Windows',
       'vadimsh', '846e3e4cb43006dbe4f026881ba8ee06835f46b1'),
      ('https://codereview.chromium.org/1051013004',
       datetime.datetime(2015, 04, 02, 01, 52, 29),
       'Also-let-cipd-support-i686-architecture', 'vadimsh',
       '8871159ca3f8d481e0e7aee7c1255fec9d5c92ee'),
      ('https://codereview.chromium.org/845263005',
       datetime.datetime(2015, 01, 13, 00, 57, 32),
       'Revert-of-Revert-Revert-of-Add-internal.DEPS-to-bot_start.-patchset-5',
       'vadimsh', 'e263ef04abaffd4e59fd9b9009bb523179212467'),
    )
    expected_out = [
      ['https://codereview.chromium.org/1051013004', '2015-04-02 01:52:29',
       'Also let cipd support i686 architecture', 'vadimsh',
       '8871159ca3f8d481e0e7aee7c1255fec9d5c92ee'],
      ['https://codereview.chromium.org/993263002', '2015-03-11 07:11:54',
      'Reland Changes in infra to get bot_setup to work on GCE Windows',
      'vadimsh', '846e3e4cb43006dbe4f026881ba8ee06835f46b1'],
      ['https://codereview.chromium.org/845263005', '2015-01-13 00:57:32',
      'Revert of Revert Revert of Add internal.DEPS to bot_start. patchset 5',
      'vadimsh', 'e263ef04abaffd4e59fd9b9009bb523179212467'],
    ]
    out = code_review_parse.get_tbr_no_lgtm(mock_cc, 'tbr')
    self.assertItemsEqual(out, expected_out)

  def test_primary_key_uniquifier(self):
    keys = [('ffa68cde441dd0f919db8f33b381df5daf9ad409', '489483',
             '2015-06-03 10:48:41',
             'https://codereview.chromium.org/1261433008', None,
             'buildbucket-InvalidInputError-on-bad-parameters'),
            ('fcfc054b7fa5c4aafd55dca5ce12422e20833430', None,
             '2015-07-31 19:52:22',
             'https://codereview.chromium.org/1060213002', None,
             'monitoring-proxy-Fixed-HTTP-status-check'),
            ('fca719d9d9f9049b02af6296a406c4699dd1cf4b ', None,
             '2015-07-31 19:52:22',
             'https://codereview.chromium.org/840743002', None,
             'buildbucket-InvalidInputError-on-bad-parameters'),
            ('ffa68cde441dd0f919db8f33b381df5daf9ad409', '471408',
             '2015-07-31 19:52:22',
             'https://codereview.chromium.org/1261433008', None,
             'Buildbucket-ereporter2-recipients')]

    unique_keys = code_review_parse.primary_key_uniquifier(keys,
        lambda x: (x[0], x[3]))
    self.assertEqual(unique_keys,
        [('ffa68cde441dd0f919db8f33b381df5daf9ad409',
          '489483', '2015-06-03 10:48:41',
          'https://codereview.chromium.org/1261433008', None,
          'buildbucket-InvalidInputError-on-bad-parameters'),
         ('fcfc054b7fa5c4aafd55dca5ce12422e20833430', None,
          '2015-07-31 19:52:22', 'https://codereview.chromium.org/1060213002',
          None, 'monitoring-proxy-Fixed-HTTP-status-check'),
         ('fca719d9d9f9049b02af6296a406c4699dd1cf4b ', None,
           '2015-07-31 19:52:22', 'https://codereview.chromium.org/840743002',
           None, 'buildbucket-InvalidInputError-on-bad-parameters')])

    no_effect = code_review_parse.primary_key_uniquifier(keys)
    self.assertEqual(no_effect,
        [('ffa68cde441dd0f919db8f33b381df5daf9ad409', '489483',
          '2015-06-03 10:48:41',
          'https://codereview.chromium.org/1261433008', None,
          'buildbucket-InvalidInputError-on-bad-parameters'),
         ('fcfc054b7fa5c4aafd55dca5ce12422e20833430', None,
          '2015-07-31 19:52:22',
          'https://codereview.chromium.org/1060213002', None,
          'monitoring-proxy-Fixed-HTTP-status-check'),
         ('fca719d9d9f9049b02af6296a406c4699dd1cf4b ', None,
          '2015-07-31 19:52:22', 'https://codereview.chromium.org/840743002',
          None, 'buildbucket-InvalidInputError-on-bad-parameters'),
         ('ffa68cde441dd0f919db8f33b381df5daf9ad409', '471408',
          '2015-07-31 19:52:22', 'https://codereview.chromium.org/1261433008',
          None,'Buildbucket-ereporter2-recipients')])