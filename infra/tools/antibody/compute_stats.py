# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json


def ratio_calculator(numerator, denominator):
  """Computes the ratio of the counts in two lists

  Args:
    numerator(list): list of lists with a year-month string as the first index
                     and a count as the second index
    denominator(list): list of lists with a year-month string as the first index
                     and a count as the second index

  Return:
    ratios(list): a list of lists with ratios rounded to three decimal places
                  e.g. [['2015-01', .251], ['2014-10', .742]]
  """
  ratios = []
  for i in numerator:
    for j in denominator:
      if i[0] == j[0] and j[1] != 0:
        ratios.append([i[0], round(float(i[1]) / j[1], 3)])
        break
      elif i[0] == j[0]:
        ratios.append([i[0], 0])
  return ratios


def totaled_ratio_calculator(numerator, denominator):
  """Computes the ratio of the counts in two lists

  Args:
    numerator(int): a totaled count
    denominator(int): a totaled count

  Return:
    ratio(float): a ratio rounded to three decimal places
  """
  if denominator != 0:
    ratio = round(float(numerator) / denominator, 3)
  else:
    ratio = 0
  return ratio


# functions that return stats calculated as lists of lists by month
def total_commits(cc):  # pragma: no cover
  """Counts all the git commits sorted by month and year

  Args:
    cc(cursor)

  Return:
    results(list): a list of lists e.g. [['2014-01', 20], ['2014-02', 45]]
  """
  cc.execute("""SELECT DISTINCT DATE_FORMAT(git_commit.timestamp, '%Y-%m')
      FROM git_commit""")
  months = cc.fetchall()
  results = []
  for month in months:
    month = month[0]
    cc.execute("""SELECT COUNT(*)
        FROM git_commit
        WHERE YEAR(git_commit.timestamp) = %s
          AND MONTH(git_commit.timestamp) = %s""" % (month[:4], month[5:]))
    result = cc.fetchone()
    results.append([month, int(result[0])])
  return results


# TODO(keelerh): group by month and year directly in the sql query instead of
# with a for loop
def total_suspicious(cc):  # pragma: no cover
  """Counts the number of commits with no review url or TBRed with no lgtm
     sorted by month and year

  Args:
    cc(cursor)

  Return:
    results(list): a list of lists
  """
  cc.execute("""SELECT DISTINCT DATE_FORMAT(git_commit.timestamp, '%Y-%m')
      FROM git_commit""")
  months = cc.fetchall()
  results = []
  for month in months:
    month = month[0]
    cc.execute("""SELECT COUNT(*)
        FROM review
        INNER JOIN git_commit
        ON review.review_url = git_commit.review_url
        INNER JOIN commit_people
        ON commit_people.git_commit_hash = git_commit.hash
        LEFT JOIN (
          SELECT review_url, COUNT(*) AS c
            FROM review_people
            WHERE type = 'lgtm'
            GROUP BY review_url) lgtm_count
        ON review.review_url = lgtm_count.review_url
        WHERE lgtm_count.c = 0 OR lgtm_count.c IS NULL
          AND commit_people.type = 'tbr'
          AND YEAR(git_commit.timestamp) = %s
          AND MONTH(git_commit.timestamp) = %s""" % (month[:4], month[5:]))
    no_lgtm = cc.fetchone()
    cc.execute("""SELECT COUNT(*)
        FROM git_commit
        WHERE review_url IS NULL
          AND YEAR(git_commit.timestamp) = %s
          AND MONTH(git_commit.timestamp) = %s""" % (month[:4], month[5:]))
    no_review = cc.fetchone()
    result = int(no_lgtm[0]) + int(no_review[0])
    results.append([month, result])
  return results


def total_tbr(cc):  # pragma: no cover
  """Counts the number of commits with a TBR

  Args:
    cc(cursor)

  Return:
    results(list): a list of lists
  """
  cc.execute("""SELECT DISTINCT DATE_FORMAT(git_commit.timestamp, '%Y-%m')
      FROM git_commit""")
  months = cc.fetchall()
  results = []
  for month in months:
    month = month[0]
    cc.execute("""SELECT COUNT(DISTINCT git_commit_hash)
        FROM commit_people
        INNER JOIN git_commit
        ON commit_people.git_commit_hash = git_commit.hash
        WHERE commit_people.type = 'tbr'
          AND YEAR(git_commit.timestamp) = %s
          AND MONTH(git_commit.timestamp) = %s""" % (month[:4], month[5:]))
    result = cc.fetchone()
    results.append([month, int(result[0])])
  return results


def tbr_no_lgtm(cc):  # pragma: no cover
  """Counts the number of commits with a TBR that have not been lgtm'ed

  Args:
    cc(cursor)

  Return:
    results(list): a list of lists
  """
  cc.execute("""SELECT DISTINCT DATE_FORMAT(git_commit.timestamp, '%Y-%m')
      FROM git_commit""")
  months = cc.fetchall()
  results = []
  for month in months:
    month = month[0]
    cc.execute("""SELECT COUNT(*)
        FROM review
        INNER JOIN git_commit ON review.review_url = git_commit.review_url
        INNER JOIN commit_people
        ON commit_people.git_commit_hash = git_commit.hash
        LEFT JOIN (
          SELECT review_url, COUNT(*) AS c FROM review_people
            WHERE type = 'lgtm' GROUP BY review_url) lgtm_count
        ON review.review_url = lgtm_count.review_url
        WHERE lgtm_count.c = 0 OR lgtm_count.c IS NULL
          AND commit_people.type = 'tbr'
          AND YEAR(git_commit.timestamp) = %s
          AND MONTH(git_commit.timestamp) = %s""" % (month[:4], month[5:]))
    result = cc.fetchone()
    results.append([month, int(result[0])])
  return results


def blank_tbr(cc):  # pragma: no cover
  """Counts the number of occurences of TBR= with no reviewer listed

  Args:
    cc(cursor)

  Return:
    results(list): a list of lists
  """
  cc.execute("""SELECT DISTINCT DATE_FORMAT(git_commit.timestamp, '%Y-%m')
      FROM git_commit""")
  months = cc.fetchall()
  results = []
  for month in months:
    month = month[0]
    cc.execute("""SELECT COUNT(*)
        FROM commit_people
        INNER JOIN git_commit
        ON commit_people.git_commit_hash = git_commit.hash
        WHERE commit_people.people_email_address = 'NOBODY'
          AND YEAR(git_commit.timestamp) = %s
          AND MONTH(git_commit.timestamp) = %s""" % (month[:4], month[5:]))
    result = cc.fetchone()
    results.append([month, int(result[0])])
  return results


def no_review_url(cc):  # pragma: no cover
  """Counts the number of commits with no review url

  Args:
    cc(cursor)

  Return:
    results(list): a list of lists
  """
  cc.execute("""SELECT DISTINCT DATE_FORMAT(git_commit.timestamp, '%Y-%m')
      FROM git_commit""")
  months = cc.fetchall()
  results = []
  for month in months:
    month = month[0]
    cc.execute("""SELECT COUNT(*)
        FROM git_commit
        WHERE review_url IS NULL
          AND YEAR(git_commit.timestamp) = %s
          AND MONTH(git_commit.timestamp) = %s""" % (month[:4], month[5:]))
    result = cc.fetchone()
    results.append([month, int(result[0])])
  return results


# functions that return totaled stats for a set period back in time
def totaled_total_commits(cc, sql_time_specification):  # pragma: no cover
  """Counts all the git commits in a given timeframe

  Args:
    cc(cursor)
    sql_time_specification(str): a sql command to limit the dates of the
                                 returned results

  Return:
    result(int): a count of all the commits
  """
  cc.execute("""SELECT COUNT(*)
      FROM git_commit
      WHERE %s""" % sql_time_specification)
  result = cc.fetchone()
  return int(result[0])


def totaled_total_suspicious(cc, sql_time_specification):  # pragma: no cover
  """Counts the number of commits with no review url or TBRed with no lgtm
     in a given timeframe

  Args:
    cc(cursor)
    sql_time_specification(str): a sql command to limit the dates of the
                                 returned results

  Return:
    result(int): a count of all the suspicious commits
  """
  cc.execute("""SELECT COUNT(*)
      FROM review
      INNER JOIN git_commit
      ON review.review_url = git_commit.review_url
      INNER JOIN commit_people
      ON commit_people.git_commit_hash = git_commit.hash
      LEFT JOIN (
        SELECT review_url, COUNT(*) AS c
          FROM review_people
          WHERE type = 'lgtm'
          GROUP BY review_url) lgtm_count
      ON review.review_url = lgtm_count.review_url
      WHERE lgtm_count.c = 0 OR lgtm_count.c IS NULL
        AND commit_people.type = 'tbr' AND %s""" % sql_time_specification)
  no_lgtm = cc.fetchone()
  cc.execute("""SELECT COUNT(*)
      FROM git_commit
      WHERE review_url IS NULL AND %s""" % sql_time_specification)
  no_review = cc.fetchone()
  result = int(no_lgtm[0]) + int(no_review[0])
  return result


def totaled_total_tbr(cc, sql_time_specification):  # pragma: no cover
  """Counts the total number of commits with a TBR in a given timeframe

  Args:
    cc(cursor)
    sql_time_specification(str): a sql command to limit the dates of the
                                 returned results

  Return:
    result(int): a count of all commits with a TBR
  """
  cc.execute("""SELECT COUNT(DISTINCT git_commit_hash)
      FROM commit_people
      INNER JOIN git_commit
      ON commit_people.git_commit_hash = git_commit.hash
      WHERE commit_people.type = 'tbr' AND %s""" % sql_time_specification)
  result = cc.fetchone()
  return int(result[0])


def totaled_tbr_no_lgtm(cc, sql_time_specification):
  """Counts the number of commits with a TBR that have not been lgtm'ed
     in a given timeframe

  Args:
    cc(cursor)
    sql_time_specification(str): a sql command to limit the dates of the
                                 returned results

  Return:
    count(int): a count of all commits with a TBR and no lgtm
    results(list): a list of lists with all tbr'ed commits with no lgtm in the
                   format [rietveld_url, git_timestamp, git_subject, git_hash]
  """
  cc.execute("""SELECT git_commit.review_url, git_commit.timestamp,
      git_commit.subject, git_commit.hash
      FROM review
      INNER JOIN git_commit
      ON review.review_url = git_commit.review_url
      INNER JOIN commit_people
      ON commit_people.git_commit_hash = git_commit.hash
      LEFT JOIN (
        SELECT review_url, COUNT(*) AS c
          FROM review_people
          WHERE type = 'lgtm'
          GROUP BY review_url) lgtm_count
      ON review.review_url = lgtm_count.review_url
      WHERE lgtm_count.c = 0 OR lgtm_count.c IS NULL
        AND commit_people.type = 'author' AND %s""" % sql_time_specification)
  result = cc.fetchall()
  count = len(result)
  formatted_data = []
  for data in result:
    subject = data[2]
    formatted_data.append([data[0], data[1].strftime("%Y-%m-%d %H:%M:%S"),
                           subject.replace('-', ' '), data[3]])
  results = sorted(formatted_data, key=lambda x: x[1], reverse=True)
  return count, results


def totaled_blank_tbr(cc, sql_time_specification):  # pragma: no cover
  """Counts the number of occurences of TBR= with no reviewer listed in a
     given timeframe

  Args:
    cc(cursor)
    sql_time_specification(str): a sql command to limit the dates of the
                                 returned results

  Return:
    count(int): a count of all blank TBRs (TBR=)
    results(list): a list of lists with all tbr'ed commits with no lgtm in the
                   format [rietveld_url, git_timestamp, git_subject, git_hash]
  """
  cc.execute("""SELECT git_commit.review_url, git_commit.timestamp,
      git_commit.subject, git_commit.hash
      FROM commit_people
      INNER JOIN git_commit
      ON commit_people.git_commit_hash = git_commit.hash
      WHERE commit_people.people_email_address = 'NOBODY'
        AND %s""" % sql_time_specification)
  result = cc.fetchall()
  count = len(result)
  formatted_data = []
  for data in result:
    subject = data[2]
    formatted_data.append([data[0], data[1].strftime("%Y-%m-%d %H:%M:%S"),
                           subject.replace('-', ' '), data[3]])
  results = sorted(formatted_data, key=lambda x: x[1], reverse=True)
  return count, results


def totaled_no_review_url(cc, sql_time_specification):   # pragma: no cover
  """Counts the number of commits with no review url in a given timeframe

  Args:
    cc(cursor)
    sql_time_specification(str): a sql command to limit the dates of the
                                 returned results

  Return:
    count(int): a count of all commits with no review_url
    results(list): a list of lists with all tbr'ed commits with no lgtm in the
                   format [rietveld_url, git_timestamp, git_subject, git_hash]
  """
  cc.execute("""SELECT git_commit.review_url, git_commit.timestamp,
      git_commit.subject, git_commit.hash
    FROM git_commit
    WHERE review_url IS NULL AND %s""" % sql_time_specification)
  result = cc.fetchall()
  count = len(result)
  formatted_data = []
  for data in result:
    subject = data[2]
    formatted_data.append([data[0], data[1].strftime("%Y-%m-%d %H:%M:%S"),
                           subject.replace('-', ' '), data[3]])
  results = sorted(formatted_data, key=lambda x: x[1], reverse=True)
  return count, results


# TODO(keelerh): change the SQL query to avoid using temporary tables
def tbr_to_total_people_ratio(cc,
                              sql_time_specification=''):  # pragma: no cover
  """Calculate TBR stats by author for the Antibody leaderboard and writes
     them to a json file

  Args:
    cc(cursor)
    sql_time_specification(str): a sql command to limit the dates of the
                                 returned results

  Return:
    people_tbr_data(list): a list of dictionaries containing author email,
                           ratio of TBRed commits to total commits, number of
                           TBRed commits, total number of commits, and overall
                           rank, reverse sorted by ratio
  """
  cc.execute("""CREATE TEMPORARY TABLE addr_tbr_hash (email VARCHAR(200), tbr
      INT, hash VARCHAR(40), `timestamp` TIMESTAMP)""")
  try:
    cc.execute("""INSERT INTO addr_tbr_hash (email, tbr, hash)
        SELECT commit_people.people_email_address, tbr_count.c,
          commit_people.git_commit_hash FROM commit_people
        LEFT JOIN (
          SELECT git_commit_hash, COUNT(*)
          AS c FROM commit_people
          INNER JOIN git_commit
          ON git_commit.hash = commit_people.git_commit_hash
          WHERE commit_people.type='tbr' %s
          GROUP BY git_commit_hash) tbr_count
        ON commit_people.git_commit_hash = tbr_count.git_commit_hash
        WHERE commit_people.type='author'""" % sql_time_specification)
    cc.execute("""SELECT email,
          SUM(CASE WHEN tbr<>0 THEN 1 ELSE 0 END) num_tbrd, COUNT(*)
        AS num_total
        FROM addr_tbr_hash
        GROUP BY email""")
    people_tbr_data = cc.fetchall()
    people_tbr_data = [[data_item[0],
                        round(float(data_item[1]) / data_item[2], 3),
                        int(data_item[1]), int(data_item[2])] for data_item in
                        people_tbr_data]
    sorted_people_tbr_data = sorted(people_tbr_data, key=lambda x: x[1],
                                    reverse=True)
    top_100 = sorted_people_tbr_data[:100]
    ordered_people_tbr_data = []
    last_ratio = None
    cur_rank = 0
    for i in range(len(top_100)):
      ratio = sorted_people_tbr_data[i][1]
      if ratio > 0:
        temp = {}
        temp['email'] = sorted_people_tbr_data[i][0]
        temp['ratio'] = ratio
        temp['suspicious'] = sorted_people_tbr_data[i][2]
        temp['total'] = sorted_people_tbr_data[i][3]
        if last_ratio != ratio:
          cur_rank += 1
        temp['rank'] = cur_rank
        last_ratio = ratio
      else:
        break
      ordered_people_tbr_data.append(temp)
  finally:
    cc.execute("""DROP TABLE addr_tbr_hash""")
  return ordered_people_tbr_data


def compute_monthly_breakdown_stats(cc):  # pragma: no cover
  """Computes stats broken down by month

  Args:
    cc(cursor)

  Returns:
    monthly_breakdown_stats(dict): contains stats calculated per month
                                   including: timeframe, total_commits,
                                   total_suspicious, suspicious_to_total_ratio,
                                   total_tbr, tbr_no_lgtm,
                                   no_tbr_lgtm_to_total_ratio, blank_tbr,
                                   blank_tbr_to_total_ratio, no_review_url,
                                   no_review_url_to_total_ratio
  """
  monthly_breakdown_stats = {}
  monthly_breakdown_stats['timeframe'] = 'monthly_breakdown'
  tot_commits = total_commits(cc)
  monthly_breakdown_stats['total_commits'] = tot_commits
  tot_suspicious = total_suspicious(cc)
  monthly_breakdown_stats['total_suspicious'] = tot_suspicious
  monthly_breakdown_stats['suspicious_to_total_ratio'] = ratio_calculator(
      tot_suspicious, tot_commits)
  tot_tbr = total_tbr(cc)
  monthly_breakdown_stats['total_tbr'] = tot_tbr
  tot_tbr_no_lgtm = tbr_no_lgtm(cc)
  monthly_breakdown_stats['tbr_no_lgtm'] = tot_tbr_no_lgtm
  monthly_breakdown_stats['no_tbr_lgtm_to_total_ratio'] = ratio_calculator(
      tot_tbr_no_lgtm, tot_tbr)
  tot_blank_tbr = blank_tbr(cc)
  monthly_breakdown_stats['blank_tbrs'] = tot_blank_tbr
  monthly_breakdown_stats['blank_tbr_to_total_ratio'] = ratio_calculator(
      tot_blank_tbr, tot_tbr)
  tot_no_review_url = no_review_url(cc)
  monthly_breakdown_stats['no_review_url'] = tot_no_review_url
  monthly_breakdown_stats['no_review_url_to_total_ratio'] = ratio_calculator(
      tot_no_review_url, tot_commits)
  return monthly_breakdown_stats


def compute_stats_by_time(cc):  # pragma: no cover
  """Computes the stats for the past 7 days, past 30 days, and all time

  Args:
    cc(cursor)

  Returns:
    output(list): three dictionaries containing stats for the past 7 days, 30
                  days, and all time respectively, each including timeframe,
                  suspicious_to_total_ratio, a count of the number of commits
                  for total_commits, tbr_no_lgtm, no_review_url, and blank_tbr,
                  and a list of lists with the relevant commits for
                  tbr_no_lgtm, no_review_url, and blank_tbr
  """
  stats_7_days = {'timeframe': '7_days'}
  stats_30_days = {'timeframe': '30_days'}
  stats_all_time = {'timeframe': 'all_time'}
  for d in [stats_7_days, stats_30_days, stats_all_time]:
    if d == stats_7_days:
      sql_insert = 'DATEDIFF(NOW(), git_commit.timestamp) <= 7'
    elif d == stats_30_days:
      sql_insert = 'DATEDIFF(NOW(), git_commit.timestamp) <= 30'
    elif d == stats_all_time:
      sql_insert = 'DATEDIFF(git_commit.timestamp, NOW()) < 0'
    tot_commits = totaled_total_commits(cc, sql_insert)
    tot_suspicious = totaled_total_suspicious(cc, sql_insert)
    d['suspicious_to_total_ratio'] = totaled_ratio_calculator(tot_suspicious,
                                                              tot_commits)
    d['total_commits'] = tot_commits
    count_tbr_no_lgtm, tbr_no_lgtm_commits = totaled_tbr_no_lgtm(cc, sql_insert)
    d['tbr_no_lgtm'] = count_tbr_no_lgtm
    d['tbr_no_lgtm_commits'] = tbr_no_lgtm_commits
    count_no_review_url, no_review_url_commits = totaled_no_review_url(
        cc, sql_insert)
    d['no_review_url'] = count_no_review_url
    d['no_review_url_commits'] = no_review_url_commits
    count_blank_tbr, blank_tbr_commits = totaled_blank_tbr(cc, sql_insert)
    d['blank_tbr'] = count_blank_tbr
    d['blank_tbr_commits'] = blank_tbr_commits
  output = [stats_7_days, stats_30_days, stats_all_time]
  return output


def all_monthly_stats(cc, filename):  # pragma: no cover
  """Write stats calculated over different time segments as json to file

  Args:
    cc(cursor)
    filename(str): the json file to write to
  """
  output = {}
  stats_monthly_breakdown = compute_monthly_breakdown_stats(cc)
  stats_by_time = compute_stats_by_time(cc)
  stats_by_time.append(stats_monthly_breakdown)
  for d in stats_by_time:
    label = d['timeframe']
    output[label] = d
  with open(filename, 'w') as f:
    json.dump(output, f)


def all_time_leaderboard(cc, filename):  # pragma: no cover
  """Writes stats for all-time Antibody leaderboard top 100 to a json file

  Args:
    cc(cursor)
    filename(str): the json file to write to
  """
  output = tbr_to_total_people_ratio(cc)
  with open(filename, 'w') as f:
    json.dump(output, f)


def past_month_leaderboard(cc, filename):  # pragma: no cover
  """Writes stats for the past month Antibody leaderboard to a json file

  Args:
    cc(cursor)
    filename(str): the json file to write to
  """
  sql_time_specification = 'AND DATEDIFF(NOW(), git_commit.timestamp) <= 30'
  output = tbr_to_total_people_ratio(cc, sql_time_specification)
  with open(filename, 'w') as f:
    json.dump(output, f)