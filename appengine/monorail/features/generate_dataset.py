"""This module is used to go from raw data to a csv dataset to build models for
   component prediction.
"""
import argparse
import string
import sys
import MySQLdb as mdb
import csv
import re
import logging
import random
import time
import os
import settings
from framework import sql
from framework import servlet

ISSUE_LIMIT = 7000
ISSUES_PER_RUN = 50
COMPONENT_PREDICTOR_PROJECT = 16

def build_component_dataset(issue, csv_file):
  """Main function to build dataset for training models.

  Args:
    data_path: The file path to store the dataset.
  """

  logging.info('Building dataset')
  con = sql.MonorailConnection()

  csv_writer = csv.writer(csv_file)

  logging.info('Downloading the dataset from database.')

  issue_table = sql.SQLTableManager('Issue')
  issue_component_table = sql.SQLTableManager('Issue2Component')
  closed_index_table = sql.SQLTableManager('ComponentIssueClosedIndex')

  close = closed_index_table.SelectValue(con, col='closed_index')

  last_close = issue_table.Select(con,
                                  cols=['closed'],
                                  where=[('closed > %s', [str(close)]),
                                         ('project_id = %s',
                                          [str(COMPONENT_PREDICTOR_PROJECT)])],
                                  order_by=[('closed', [])],
                                  limit=ISSUE_LIMIT)[-1][0]

  issue_ids = issue_table.Select(con,
                              cols=['id'],
                              where=[('closed > %s', [str(close)]),
                                     ('closed <= %s', [str(last_close)]),
                                     ('project_id = %s',
                                      [str(COMPONENT_PREDICTOR_PROJECT)])])


  logging.info('Close: ' + str(close))
  logging.info('Last close: ' + str(last_close))

  # Get the comments and components for 50 issues at a time so as to not
  # overwhelm a single shard with all 5000 issues at once
  for i in range(0, len(issue_ids), ISSUES_PER_RUN):
    issue_list = [str(x[0]) for x in issue_ids[i:i+ISSUES_PER_RUN]]

    comments = issue.GetCommentsForIssues(con, issue_list, content_only=True)

    shard_id = random.randint(0, settings.num_logical_shards - 1)

    components = issue_component_table.Select(con,
                                        cols=['issue_id',
                                              'GROUP_CONCAT(component_id '
                                              + 'SEPARATOR \',\')'],
                                        joins=[('ComponentDef ON '
                                                'ComponentDef.id = '
                                                'Issue2Component.component_id',
                                                [])],
                                        where=[('(deprecated = %s OR deprecated'
                                                ' IS NULL)', [False])],
                                        group_by=['issue_id'],
                                        shard_id=shard_id,
                                        issue_id=issue_list)

    for issue_id, component_ids in components:
      comment_string = ' '.join(
          [comment.content for comment in comments[issue_id]])

      pretty_issue = comment_string.lower().strip()

      no_punctuation_issue = re.sub('[^\w\s]|_+', '', pretty_issue)
      one_space_issue = ' '.join(no_punctuation_issue.split())

      final_issue = component_ids, one_space_issue
      csv_writer.writerow(final_issue)

  closed_index_table.Update(con, delta={'closed_index' : last_close})

  return csv_file
