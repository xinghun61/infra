# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Cron job that adds all new user commmits to the SQL database daily."""

import calendar
import json
import logging
from datetime import datetime

import settings
from framework import jsonfeed
from google.appengine.api import urlfetch

class GetCommitsCron(jsonfeed.InternalTask):
  """Fetches commit data from Gitiles and adds it to the CloudSQL
  database
  """
  def HandleRequest(self, mr):
    """Update/Delete rows from the UserCommits table as needed.

    Args:
      mr: common information parsed from the HTTP request.

    Returns:
      Nothing.
    """
    for repo_url in settings.usercommits_repo_urls:
      if not repo_url.endswith('/'):
        repo_url = repo_url + '/'
      row_values = []
      most_recent_commit_in_table = self.services.user.usercommits_tbl.Select(
          mr.cnxn,
          cols=['commit_sha'],
          where=[('UserCommits.commit_repo_url = %s', [repo_url])],
          order_by=[('commit_time DESC', [])],
          limit=1)

      if not most_recent_commit_in_table:
        try:
          row_values = self.InitializeRepo(mr.cnxn, repo_url)
        except Exception as e:
          logging.info('Initializing repo %s failed: %s', repo_url, e)
          continue
      else:
        try:
          row_values = self.UpdateRepo(mr.cnxn, repo_url,
            most_recent_commit_in_table)
        except Exception as e:
          logging.info('Updating repo %s failed: %s', repo_url, e)
          continue
    self.AddToDatabase(mr.cnxn, row_values)
    self.DropRows(mr.cnxn)

  def AddToDatabase(self, cnxn, row_values):
    """Adds new rows to the UserCommits table."""
    cols = ["commit_sha", "author_id", "commit_time",
      "commit_message", "commit_repo_url"]
    self.services.user.usercommits_tbl.InsertRows(cnxn, cols,
        row_values, ignore=True)

  def DropRows(self, cnxn):
    """Drops the oldest commits if the table is over the max number of rows."""
    old_count = self.services.user.usercommits_tbl.SelectValue(cnxn,
        'COUNT(*)')
    if old_count > settings.max_rows_in_usercommits_table:
      order_by = [('commit_time DESC', [])]
      to_delete = self.services.user.usercommits_tbl.Select(cnxn,
          cols=['commit_sha'],
          order_by=order_by,
          offset=settings.max_rows_in_usercommits_table,
          limit=18446744073709551615)
      to_delete = [item[0] for item in to_delete]
      self.services.user.usercommits_tbl.Delete(cnxn,
        commit_sha=to_delete)

  def FetchGitilesData(self, url):
    """Gets the JSON from Gitiles and returns it as a dict.

    Args:
      url: url to get data from. The url passed in already has an incomplete
      query string (either just '?' or '?foo=bar&') since the 'format=JSON' is
      added

    Returns: The JSON data as a Python object
    """
    response = {}
    attempts = 0
    backoff_time = 0.1
    while attempts < 4:
      attempts += 1
      try:
        result = urlfetch.fetch(url + 'format=JSON')
      except (urlfetch.Error) as e:
        logging.warning('GET %s failed: %s', url, e)
        continue
      if result.status_code == 200:
        content = result.content
        try:
          # This line is to strip out the XSSI prefix for Gitiles
          if content.startswith(")]}'\n"):
            content = content[5:]
          response = json.loads(content)
        except ValueError as e:
          logging.warning('Bad JSON response: %s' % e)
        return response
      else:
        logging.warning(
            'GET %s failed, HTTP %d: %r', url, result.status_code,
            result.content)
      time.sleep(self.backoff_time)
      backoff_time *= 2
    raise Exception('Failed to GET %s after multiple attempts' % url)

  def _ConvertCommitTime(self, commit_time):
    """Takes in time as string and converts it to Unix time."""
    converted_time = datetime.strptime(commit_time,
        '%b %d %H:%M:%S %Y')
    converted_time = calendar.timegm(converted_time.timetuple())
    return converted_time

  def InitializeRepo(self, cnxn, repo_url):
    """Backfill a table with commits when a new repo is added.

    Args:
      cnxn: connection to the DB.
      repo_url: url of the repo that we will be adding commits from.

    Returns: A list of lists where each list is a new row for the UserCommits
    table.
    """
    row_values = []
    adding_new_commits = True
    url = repo_url + '+log/?'

    oldest_commit_in_table = self.services.user.usercommits_tbl.SelectRow(
        cnxn,
        cols=['commit_time'],
        order_by=[('commit_time', [])],
        limit=1)
    empty_table = True
    oldest_commit_in_table_time = 0
    if oldest_commit_in_table:
      empty_table = False
      oldest_commit_in_table_time = oldest_commit_in_table[0]

    while adding_new_commits:
      response = self.FetchGitilesData(url)
      for commit in response['log']:
        commit_time = self._ConvertCommitTime(commit['author']['time'][4:])
        author_id = self.services.user.LookupUserID(
            cnxn, commit['author']['email'], autocreate=True)
        if ((len(row_values) < settings.usercommits_backfill_max) and
           (empty_table or (commit_time > oldest_commit_in_table_time))):
          row_values.append([commit['commit'],
              author_id,
              commit_time,
              commit['message'],
              repo_url])
        else:
          adding_new_commits = False
          break
      if 'next' not in response:
        adding_new_commits = False
      if adding_new_commits:
        url = repo_url + '+log/?' + 's=' + response['next'] + '&'
    return row_values

  def UpdateRepo(self, cnxn, repo_url, most_recent_commit_in_table):
    """Add new commits to the table to keep it updated.

    Args:
      cnxn: connection to the DB.
      repo_url: url of the repo that we will be adding commits from.

    Returns: A list of lists where each list is a new row for the UserCommits
    table.
    """
    row_values = []
    adding_new_commits = True
    url = repo_url + '+log/?'
    last_added_commit = most_recent_commit_in_table[0][0]

    while adding_new_commits:
      response = self.FetchGitilesData(url)
      for commit in response['log']:
        commit_time = self._ConvertCommitTime(commit['author']['time'][4:])
        author_id = self.services.user.LookupUserID(
            cnxn, commit['author']['email'], autocreate=True)
        if commit['commit'] != last_added_commit:
          row_values.append([commit['commit'],
              author_id,
              commit_time,
              commit['message'],
              repo_url])
        else:
          adding_new_commits = False
          break
      if 'next' not in response:
        adding_new_commits = False
      if adding_new_commits:
        url = repo_url + '+log/?' + 's=' + response['next'] + '&'
    return row_values
