"""Compose a markdown file reporting the results of the experiments.

This script looks at all the experiment files in the directory given as the
first argument.

The report is then saved in the path specified as second argument, or output to
stdout otherwise.
"""
import glob
import json
import os
import sys
import textwrap

SWARM_HOST = 'https://chromium-swarm.appspot.com'


def generate_report(data_path):
  data_path = data_path or os.path.dirname(__file__)

  # findings will map each experiment to a dict that will map the datapoint
  # (labeled as 'findit_stable' or 'findit_culprit') to  a string describing
  # whether the experiment found it to be stable or flaky.
  findings = {}
  analyses_details = []
  for data_file in glob.glob(os.path.join(data_path, 'experiment-*.json')):
    data = json.load(open(data_file))
    # Derive the test name from the gtest_filter.
    data['test_name'] = [
        x.split('=')[1]
        for x in data['additional_args_template'].split()
        if x.startswith('--gtest_filter=')
    ][0]
    data['extra_args'] = (
        data['additional_args_template'] % data['repeats_per_task'])
    findings[data_file], detail_body = make_analysis_detail(data)
    analyses_details.append(detail_body)

  tally, tally_table = tally_up(findings)

  summary = textwrap.dedent("""## Summary

      In {MORE SENSITIVE THAN FINDIT} of the cases, running separate tasks
      reproduced the flakiness in both the point considered stable and the point
      considered flaky by findit. That is, the flakiness is more easily
      observable by launching separate jobs where each executes on test run.
      Classified below as 'MORE SENSITIVE THAN FINDIT'

      In  {LESS SENSITIVE THAN FINDIT} of the cases, running separate tasks
      failed to reproduce flakiness on both the stable and flaky revision (as
      labeled by findit). That is, the flakiness is observable when running the
      tests several times in the same job, but not when running it in separate
      jobs. Labeled as 'LESS SENSITIVE THAN FINDIT'

      In {JUST AS SENSITIVE AS FINDIT} of the cases, the separate tasks
      performed similarly to Findit, and would have arrived at the same
      conclusion. Labeled as 'JUST AS SENSITIVE AS FINDIT'. These are perhaps
      true positives.

      In {WTF} of the cases, the experiment determined that the revision
      considered stable by Findit, was indeed flaky, but paradoxically was
      unable to reproduce this flakiness on the revision that Findit classified
      as flaky. These cases are labeled as WTF ("Weirder Than Findit") Below"""
                           ).format(**tally)

  return '\n'.join([summary, tally_table] + analyses_details)


def make_analysis_detail(data):
  """Makes a md snippet describing the experiment details for a single analysis.
  """
  detail_body = ''
  build_id = '{master_name}/{builder_name}/{build_number}'
  analysis_link = (
      'https://analysis.chromium.org'
      '/p/chromium/flake-portal/analysis/analyze?key={analysis_key}')
  analysis_result = {'findit_stable': '', 'findit_culprit': ''}
  for row in data['rows']:
    revision_results = row['results']
    revision_results['stable'] = 'stable' if row['expected_stable'] else 'flaky'
    revision_results['isolate_hash'] = row['isolate_hash']
    revision_results['total_failures'] = (
        revision_results['total_tries'] - revision_results['total_passes'])
    flake_bots = sorted(revision_results.get('not_all_pass_bots', []))
    stable_bots = sorted(revision_results.get('all_pass_bots', []))
    analysis_result[
        'findit_stable' if row['expected_stable'] else 'findit_culprit'] = (
            'experiment_stable' if not flake_bots else 'experiment_flaky')
    # It is unreadable to list all bots used to run the experiments' tasks,
    # just list the first and last (lexicographically) in the set.
    revision_results['flake_bots'] = '...'.join(
        [flake_bots[0], flake_bots[-1]]) if len(flake_bots) > 1 else flake_bots
    revision_results['stable_bots'] = '...'.join([
        stable_bots[0], stable_bots[-1]
    ]) if len(stable_bots) > 1 else stable_bots

    # Link to example passing and failing tasks.
    revision_results['fail_example'] = ''
    revision_results['pass_example'] = ''
    if flake_bots:
      for task, task_result in row['task_results'].iteritems():
        if task_result.get('failures'):
          revision_results['fail_example'] = '[%s](%s/task?id=%s)' % (
              task, SWARM_HOST, task)
    if stable_bots:
      for task, task_result in row['task_results'].iteritems():
        if task_result.get('passes'):
          revision_results['pass_example'] = '[%s](%s/task?id=%s)' % (
              task, SWARM_HOST, task)

    detail_body += ('\n\n#### Isolated hash:{isolate_hash}\n'
                    '\n- Findit thought this revision was *{stable}*'
                    '\n- Out of {total_tries}:'
                    '\n  - {total_passes} passed'
                    '\n    - Bots: {stable_bots}'
                    '\n    - Example: {pass_example}'
                    '\n  - {total_failures} failed'
                    '\n    - Bots: {flake_bots}'
                    '\n    - Example: {fail_example}').format(
                        **revision_results)
  detail_header = ('\n\n### {label}: Analysis for flake on '
                   '[' + build_id + '](' + analysis_link + ')'
                   '\n\nTest name: ```{test_name}```'
                   '\n\nDimensions: ```{dimensions}```'
                   '\n\nExtra args: ```{extra_args}```').format(
                       label=make_label(analysis_result['findit_stable'],
                                        analysis_result['findit_culprit']),
                       **data)
  return analysis_result, '\n'.join([detail_header, detail_body])


def tally_up(findings):
  tally_lines = []
  tally = {}
  for label in [
      'MORE SENSITIVE THAN FINDIT', 'LESS SENSITIVE THAN FINDIT',
      'JUST AS SENSITIVE AS FINDIT', 'WTF'
  ]:
    tally.setdefault(label, 0)

  for k, v in findings.iteritems():
    v['result'] = make_label(v['findit_stable'], v['findit_culprit'])
    tally[v['result']] += 1

  tally_lines.append('')
  tally_lines.append('| Result | Tally |')
  tally_lines.append('| ------ | ----- |')
  for k in [
      'MORE SENSITIVE THAN FINDIT', 'LESS SENSITIVE THAN FINDIT',
      'JUST AS SENSITIVE AS FINDIT', 'WTF'
  ]:
    v = tally[k]
    tally_lines.append('| %s | %d |' % (k, v))
  return tally, '\n'.join(tally_lines)


def make_label(findit_stable, findit_culprit):
  if findit_stable == 'experiment_stable':
    if findit_culprit == 'experiment_flaky':
      # Separate tasks agree with findit.
      result = 'JUST AS SENSITIVE AS FINDIT'
    else:
      # Separate tasks won't increase accuracy.
      result = 'LESS SENSITIVE THAN FINDIT'
  else:
    if findit_culprit == 'experiment_flaky':
      # Separate tasks will increase accuracy
      result = 'MORE SENSITIVE THAN FINDIT'
    else:
      result = 'WTF'  # Watch this finding.
  return result


def main():
  data_path = sys.argv[1] if len(sys.argv) > 1 else None
  report = generate_report(data_path)
  if len(sys.argv) == 3:
    open(sys.argv[2], 'w').write(report)
  else:
    print report
  return 0


if __name__ == '__main__':
  sys.exit(main())
