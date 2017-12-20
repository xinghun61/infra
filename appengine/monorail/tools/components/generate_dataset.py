"""This module is used to go from raw data to a csv dataset to build models for
   component prediction.
"""
import argparse
import string
from bs4 import BeautifulSoup
import MySQLdb as mdb
import csv
import re
import logging

def build_component_dataset(host, user, password, data_path):
  """Main function to build dataset for training models.

  Args:
    host: The location of the database that is being connected to.
    user: The user name to connect to the database.
    password: The user's password.
    data_path: The file path to store the dataset.
  """
  connection = mdb.connect(host=host,
                           user=user,
                           passwd=password,
                           db="monorail")

  csv_file = open(data_path, "w+")

  csv_writer = csv.writer(csv_file)

  logging.info("Downloading the dataset.")

  # For each issue, get component ids and concatenated issue comment content
  connection.query("""SELECT
                   GROUP_CONCAT(ComponentDef.id SEPARATOR ',') AS ComponentIds,
                   GROUP_CONCAT(CommentContent.content SEPARATOR ' ')
                   AS Comments FROM Issue2Component, Issue, ComponentDef,
                   Comment, CommentContent WHERE
                   Issue2Component.issue_id = Issue.id
                   AND ComponentDef.id = Issue2Component.component_id
                   AND Comment.issue_id = Issue.id
                   AND Comment.commentcontent_id = CommentContent.id
                   AND Issue.closed != 0
                   AND Issue.project_id = 16
                   GROUP BY Issue.id""")

  results = connection.use_result()

  issue = results.fetch_row()

  while issue:
    pretty_issue = BeautifulSoup(issue[0][1]).get_text() \
                                             .lower() \
                                             .strip() \
                                             .encode('utf8')
    no_punctuation_issue = re.sub('[^\w\s]|_+', '', pretty_issue)
    one_space_issue = " ".join(no_punctuation_issue.split())
    final_issue = issue[0][0], one_space_issue
    csv_writer.writerow(final_issue)
    issue = results.fetch_row()


if __name__ == "__main__":
  parser = argparse.ArgumentParser()

  parser.add_argument("host")
  parser.add_argument("user")
  parser.add_argument("password")
  parser.add_argument("data_path")
  args = parser.parse_args()

  build_component_dataset(args.host, args.user, args.password, args.data_path)
