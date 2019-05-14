# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Tests for the UserCommits module."""

import unittest

import mock
import mox

from mock import Mock

from google.appengine.api import urlfetch

import settings
from sitewide import usercommits
from framework import sql
from services import service_manager
from testing import fake
from testing import testing_helpers

class UserCommitsTest(unittest.TestCase):

  def setUp(self):
    self.mox = mox.Mox()
    self.cnxn = fake.MonorailConnection()
    self.user_service = fake.UserService()
    self.services = service_manager.Services(
        user=fake.UserService())
    self.services.user.usercommits_tbl = (
        self.mox.CreateMock(sql.SQLTableManager))
    self.mox.StubOutWithMock(settings, 'usercommits_backfill_max')
    self.mox.StubOutWithMock(settings, 'max_rows_in_usercommits_table')
    settings.max_rows_in_usercommits_table = 2
    self.mox.StubOutWithMock(settings, 'usercommits_repo_urls')
    settings.usercommits_repo_urls = (
        ['https://chromium.googlesource.com/infra/infra/'])

    self.gitiles_json_dict = {
      "log": [
        {
          "commit": "96753d0ac9dba51216be0c94d198a5c0103d0146",
          "tree": "f9d698d8fbe84784e6ad8393926864e3609aa52c",
          "parents": [
            "3a23146c0e8ca48461330fb280c8c241722aa1a4"
          ],
          "author": {
            "name": "C",
            "email": "c@chromium.org",
            "time": "Wed Jul 18 21:45:28 2018"
          },
          "committer": {
            "name": "recipe-roller",
            "email": "recipe-roller@chromium.org",
            "time": "Wed Jul 18 21:45:28 2018"
          },
          "message": "message C"
        },
        {
          "commit": "3a23146c0e8ca48461330fb280c8c241722aa1a4",
          "tree": "9ca17df4e9eda6ad4ad40d51f51f752cf8ca6a05",
          "parents": [
            "671b868f34028bd58b05fd91a664fb4b21c8ecf0"
          ],
          "author": {
            "name": "B",
            "email": "b@chromium.org",
            "time": "Wed Jul 18 21:29:28 2018"
          },
          "committer": {
            "name": "recipe-roller",
            "email": "recipe-roller@chromium.org",
            "time": "Wed Jul 18 21:29:28 2018"
          },
          "message": "message B"
        },
        {
          "commit": "671b868f34028bd58b05fd91a664fb4b21c8ecf0",
          "tree": "7a02e6c4c492e380d69dc1ccd8ffdfd52e59fff6",
          "parents": [
            "7f4c64d9c74ddae70703faeda4986629d7d8dee8"
          ],
          "author": {
            "name": "A",
            "email": "a@chromium.org",
            "time": "Wed Jul 18 20:57:07 2018"
          },
          "committer": {
            "name": "recipe-roller",
            "email": "recipe-roller@chromium.org",
            "time": "Wed Jul 18 20:57:07 2018"
          },
          "message": "message A"
        }
      ],
      "next": "54f489631b5337df4cb3f0a94f06a840b53db0ac"
    }

    self.gitiles_json_dict_next = {
      "log": [
        {
          "commit": "54f489631b5337df4cb3f0a94f06a840b53db0ac",
          "tree": "26af381b15ff3e05219145f8290cee6e834cc190",
          "parents": [
            "7943d2b4e0caad67dd6dd917c892157f31cb8326"
          ],
          "author": {
            "name": "D",
            "email": "d@chromium.org",
            "time": "Wed Jul 18 19:45:28 2018"
          },
          "committer": {
            "name": "recipe-roller",
            "email": "recipe-roller@chromium.org",
            "time": "Wed Jul 18 19:45:28 2018"
          },
          "message": "message D"
        },
        {
          "commit": "a37d2b00df7a0abd2867aeb427f72f3bdaa6f16c",
          "tree": "9ca17df4e9eda6ad4ad40d51f51f752cf8ca6a05",
          "parents": [
            "671b868f34028bd58b05fd91a664fb4b21c8ecf0"
          ],
           "author": {
             "name": "E",
             "email": "e@chromium.org",
             "time": "Wed Jul 18 13:45:28 2018"
           },
           "committer": {
             "name": "recipe-roller",
             "email": "recipe-roller@chromium.org",
             "time": "Wed Jul 18 13:45:28 2018"
           },
           "message": "message E"
         }
      ]
    }

    self.gitiles_json = """)]}'
    {
      "log": [
        {
          "commit": "4ad9264f78b563ed20ebf74d2ce739df6c9a1d6e"
        }
   }"""



  def SetUpDropRows_OverLimit(self):
    settings.usercommits_backfill_max = 2
    self.services.user.usercommits_tbl.SelectValue(self.cnxn,
        'COUNT(*)').AndReturn(1)

  def testDropRows_OverLimit(self):
    self.SetUpDropRows_OverLimit()
    usercommitscron = usercommits.GetCommitsCron('req', 'resp',
        services=self.services)
    self.mox.ReplayAll()
    usercommitscron.DropRows(self.cnxn)
    self.mox.VerifyAll()

  def SetUpInitializeRepo_PopulatedTable(self, usercommitscron):
    settings.usercommits_backfill_max = 2
    self.services.user.usercommits_tbl.SelectRow(
        self.cnxn,
        cols=['commit_time'],
        order_by=[('commit_time', [])],
        limit=1).AndReturn((1531949368,))
    self.mox.StubOutWithMock(usercommitscron, "FetchGitilesData")
    usercommitscron.FetchGitilesData(
        "https://chromium.googlesource.com/infra/infra/+log/?").AndReturn(
        self.gitiles_json_dict)
    self.mox.StubOutWithMock(self.services.user, "LookupUserID")
    self.services.user.LookupUserID(
        self.cnxn, "c@chromium.org", autocreate=True).AndReturn(int(3))
    self.services.user.LookupUserID(
        self.cnxn, "b@chromium.org", autocreate=True).AndReturn(int(2))

  def testInitializeRepo_PopulatedTable(self):
    usercommitscron = usercommits.GetCommitsCron('req', 'resp',
        services=self.services)
    self.SetUpInitializeRepo_PopulatedTable(usercommitscron)
    self.mox.ReplayAll()
    rows = usercommitscron.InitializeRepo(self.cnxn,
        'https://chromium.googlesource.com/infra/infra/')
    self.mox.VerifyAll()
    self.assertEquals([
        ["96753d0ac9dba51216be0c94d198a5c0103d0146",3,1531950328, "message C",
        "https://chromium.googlesource.com/infra/infra/"],
        ], rows)

  def SetUpInitializeRepo_EmptyTable(self, usercommitscron):
    settings.usercommits_backfill_max = 2
    self.services.user.usercommits_tbl.SelectRow(
        self.cnxn,
        cols=['commit_time'],
        order_by=[('commit_time', [])],
        limit=1).AndReturn(None)
    self.mox.StubOutWithMock(usercommitscron, "FetchGitilesData")
    usercommitscron.FetchGitilesData(
        "https://chromium.googlesource.com/infra/infra/+log/?").AndReturn(
        self.gitiles_json_dict)
    self.mox.StubOutWithMock(self.services.user, "LookupUserID")
    self.services.user.LookupUserID(
        self.cnxn, "c@chromium.org", autocreate=True).AndReturn(int(3))
    self.services.user.LookupUserID(
        self.cnxn, "b@chromium.org", autocreate=True).AndReturn(int(2))
    self.services.user.LookupUserID(
        self.cnxn, "a@chromium.org", autocreate=True).AndReturn(int(1))

  def testInitializeRepo_EmptyTable(self):
    usercommitscron = usercommits.GetCommitsCron('req', 'resp',
        services=self.services)
    self.SetUpInitializeRepo_EmptyTable(usercommitscron)
    self.mox.ReplayAll()
    rows = usercommitscron.InitializeRepo(self.cnxn,
        'https://chromium.googlesource.com/infra/infra/')
    self.mox.VerifyAll()
    self.assertEquals([
        ["96753d0ac9dba51216be0c94d198a5c0103d0146",3,1531950328, "message C",
        "https://chromium.googlesource.com/infra/infra/"],
        ["3a23146c0e8ca48461330fb280c8c241722aa1a4", 2,1531949368, "message B",
        "https://chromium.googlesource.com/infra/infra/"]
        ], rows)

  def SetUpInitializeRepo_AddFromNextPage(self, usercommitscron):
    settings.usercommits_backfill_max = 4
    self.services.user.usercommits_tbl.SelectRow(
        self.cnxn,
        cols=['commit_time'],
        order_by=[('commit_time', [])],
        limit=1).AndReturn(None)
    self.mox.StubOutWithMock(usercommitscron, "FetchGitilesData")
    usercommitscron.FetchGitilesData(
        "https://chromium.googlesource.com/infra/infra/+log/?").AndReturn(
        self.gitiles_json_dict)
    self.mox.StubOutWithMock(self.services.user, "LookupUserID")
    self.services.user.LookupUserID(
        self.cnxn, "c@chromium.org", autocreate=True).AndReturn(int(3))
    self.services.user.LookupUserID(
        self.cnxn, "b@chromium.org", autocreate=True).AndReturn(int(2))
    self.services.user.LookupUserID(
        self.cnxn, "a@chromium.org", autocreate=True).AndReturn(int(1))
    nexturl = ("https://chromium.googlesource.com/infra/infra/+log/?"
        +"s=54f489631b5337df4cb3f0a94f06a840b53db0ac&")
    usercommitscron.FetchGitilesData(
        nexturl).AndReturn(
        self.gitiles_json_dict_next)
    self.services.user.LookupUserID(
        self.cnxn, "d@chromium.org", autocreate=True).AndReturn(int(4))
    self.services.user.LookupUserID(
        self.cnxn, "e@chromium.org", autocreate=True).AndReturn(int(5))

  def testInitializeRepo_AddFromNextPage(self):
    usercommitscron = usercommits.GetCommitsCron('req', 'resp',
        services=self.services)
    self.SetUpInitializeRepo_AddFromNextPage(usercommitscron)
    self.mox.ReplayAll()
    rows = usercommitscron.InitializeRepo(self.cnxn,
        'https://chromium.googlesource.com/infra/infra/')
    self.mox.VerifyAll()
    self.assertEquals([
        ["96753d0ac9dba51216be0c94d198a5c0103d0146", 3,1531950328, "message C",
        "https://chromium.googlesource.com/infra/infra/"],
        ["3a23146c0e8ca48461330fb280c8c241722aa1a4", 2,1531949368, "message B",
        "https://chromium.googlesource.com/infra/infra/"],
        ["671b868f34028bd58b05fd91a664fb4b21c8ecf0", 1,1531947427, "message A",
        "https://chromium.googlesource.com/infra/infra/"],
        ["54f489631b5337df4cb3f0a94f06a840b53db0ac", 4,1531943128, "message D",
        "https://chromium.googlesource.com/infra/infra/"]
        ], rows)

  def SetUpUpdateRepo(self, usercommitscron):
    self.mox.StubOutWithMock(usercommitscron, "FetchGitilesData")
    usercommitscron.FetchGitilesData(
        "https://chromium.googlesource.com/infra/infra/+log/?").AndReturn(
        self.gitiles_json_dict)
    self.mox.StubOutWithMock(self.services.user, "LookupUserID")
    self.services.user.LookupUserID(
        self.cnxn, "c@chromium.org", autocreate=True).AndReturn(int(3))
    self.services.user.LookupUserID(
        self.cnxn, "b@chromium.org", autocreate=True).AndReturn(int(2))
    self.services.user.LookupUserID(
        self.cnxn, "a@chromium.org", autocreate=True).AndReturn(int(1))

  def testUpdateRepo(self):
    usercommitscron = usercommits.GetCommitsCron('req', 'resp',
        services=self.services)
    self.SetUpUpdateRepo(usercommitscron)
    self.mox.ReplayAll()
    rows = usercommitscron.UpdateRepo(self.cnxn,
        'https://chromium.googlesource.com/infra/infra/',
        [('671b868f34028bd58b05fd91a664fb4b21c8ecf0',)])
    self.mox.VerifyAll()
    self.assertEquals([
        ["96753d0ac9dba51216be0c94d198a5c0103d0146",3,1531950328, "message C",
        "https://chromium.googlesource.com/infra/infra/"],
        ["3a23146c0e8ca48461330fb280c8c241722aa1a4", 2,1531949368, "message B",
        "https://chromium.googlesource.com/infra/infra/"]
        ], rows)

  def SetUpUpdateRepo_AddFromNextPage(self, usercommitscron):
    self.mox.StubOutWithMock(usercommitscron, "FetchGitilesData")
    usercommitscron.FetchGitilesData(
        "https://chromium.googlesource.com/infra/infra/+log/?").AndReturn(
        self.gitiles_json_dict)
    self.mox.StubOutWithMock(self.services.user, "LookupUserID")
    self.services.user.LookupUserID(
        self.cnxn, "c@chromium.org", autocreate=True).AndReturn(int(3))
    self.services.user.LookupUserID(
        self.cnxn, "b@chromium.org", autocreate=True).AndReturn(int(2))
    self.services.user.LookupUserID(
        self.cnxn, "a@chromium.org", autocreate=True).AndReturn(int(1))
    nexturl = ("https://chromium.googlesource.com/infra/infra/+log/?"
        +"s=54f489631b5337df4cb3f0a94f06a840b53db0ac&")
    usercommitscron.FetchGitilesData(
        nexturl).AndReturn(
        self.gitiles_json_dict_next)
    self.services.user.LookupUserID(
        self.cnxn, "d@chromium.org", autocreate=True).AndReturn(int(4))
    self.services.user.LookupUserID(
        self.cnxn, "e@chromium.org", autocreate=True).AndReturn(int(5))

  def testUpdateRepo_AddFromNextPage(self):
    usercommitscron = usercommits.GetCommitsCron('req', 'resp',
        services=self.services)
    self.SetUpUpdateRepo_AddFromNextPage(usercommitscron)
    self.mox.ReplayAll()
    rows = usercommitscron.UpdateRepo(self.cnxn,
        'https://chromium.googlesource.com/infra/infra/',
        [('a37d2b00df7a0abd2867aeb427f72f3bdaa6f16c',)])
    self.mox.VerifyAll()
    self.assertEquals([
        ["96753d0ac9dba51216be0c94d198a5c0103d0146", 3,1531950328, "message C",
        "https://chromium.googlesource.com/infra/infra/"],
        ["3a23146c0e8ca48461330fb280c8c241722aa1a4", 2,1531949368, "message B",
        "https://chromium.googlesource.com/infra/infra/"],
        ["671b868f34028bd58b05fd91a664fb4b21c8ecf0", 1,1531947427, "message A",
        "https://chromium.googlesource.com/infra/infra/"],
        ["54f489631b5337df4cb3f0a94f06a840b53db0ac", 4,1531943128, "message D",
        "https://chromium.googlesource.com/infra/infra/"]
        ], rows)

  def SetUpFetchGitilesData_UrlError(self):
    self.mox.StubOutWithMock(urlfetch, "fetch")
    urlfetch.fetch(
        'https://chromium.googlesource.com/infra/infra/format=JSON').AndRaise(
        urlfetch.Error('Broken')
    )
    urlfetch.fetch(
        'https://chromium.googlesource.com/infra/infra/format=JSON').AndRaise(
        urlfetch.Error('Broken')
    )
    urlfetch.fetch(
        'https://chromium.googlesource.com/infra/infra/format=JSON').AndRaise(
        urlfetch.Error('Broken')
    )
    urlfetch.fetch(
        'https://chromium.googlesource.com/infra/infra/format=JSON').AndRaise(
        urlfetch.Error('Broken')
    )

  def testFetchGitilesData_UrlError(self):
    usercommitscron = usercommits.GetCommitsCron('req', 'resp',
        services=self.services)
    self.SetUpFetchGitilesData_UrlError()
    self.mox.ReplayAll()
    self.assertRaises(Exception, usercommitscron.FetchGitilesData,
        "https://chromium.googlesource.com/infra/infra/")
    self.mox.VerifyAll()

  def SetUpFetchGitilesData_JSONError(self):
    self.mox.StubOutWithMock(urlfetch, "fetch")
    urlfetch.fetch(
        'https://chromium.googlesource.com/infra/infra/format=JSON').AndReturn(
        {})

  def testFetchGitilesData_JSONError(self):
    usercommitscron = usercommits.GetCommitsCron('req', 'resp',
        services=self.services)
    self.SetUpFetchGitilesData_JSONError()
    self.mox.ReplayAll()
    self.assertRaises(Exception, usercommitscron.FetchGitilesData,
        "https://chromium.googlesource.com/infra/infra/")
    self.mox.VerifyAll()

  def SetUpFetchGitilesData(self):
    self.mox.StubOutWithMock(urlfetch, "fetch")
    class fakeresponse:
      content = self.gitiles_json
      status_code = 200
    urlfetch.fetch(
        'https://chromium.googlesource.com/infra/infra/format=JSON').AndReturn(
        fakeresponse())

  def testFetchGitilesData(self):
    usercommitscron = usercommits.GetCommitsCron('req', 'resp',
        services=self.services)
    self.SetUpFetchGitilesData()
    self.mox.ReplayAll()
    usercommitscron.FetchGitilesData(
        "https://chromium.googlesource.com/infra/infra/")
    self.mox.VerifyAll()
