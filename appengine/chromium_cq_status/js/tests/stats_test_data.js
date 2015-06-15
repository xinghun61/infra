// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

var stats_test_data = {
  "cursor": "CkYKEgoFYmVnaW4SCQiA4KDXkdbFAhIsahRzfmNocm9taXVtLWNxLXN0YXR1c3IUCxIHQ1FTdGF0cxiAgIDihtCbCwwYACAB",
  "results": [
    {
      "begin": 1434146400,
      "end": 1434150000,
      "interval_minutes": 60,
      "project": "infra",
      "key": 5118706493423616,
      "stats": [
        {
          "count": 0,
          "type": "count",
          "name": "tryjobverifier-skip-count",
          "description": "Number of tryjob verifier runs skipped."
        },
        {
          "count": 3,
          "type": "count",
          "name": "patchset-count",
          "description": "Number of patchsets processed by the CQ."
        },
        {
          "count": 2,
          "type": "count",
          "name": "patchset-commit-count",
          "description": "Number of patchsets committed by the CQ."
        },
        {
          "count": 2,
          "type": "count",
          "name": "tryjobverifier-pass-count",
          "description": "Number of tryjob verifier runs passed."
        },
        {
          "count": 0,
          "type": "count",
          "name": "patchset-false-reject-count",
          "description": "Number of patchsets rejected by the trybots that eventually passed."
        },
        {
          "count": 2,
          "type": "count",
          "name": "trybot-pass-count",
          "description": "Number of passing runs across all trybots."
        },
        {
          "count": 1,
          "type": "count",
          "name": "trybot-infra_tester-fail-count",
          "description": "Number of failing runs by the infra_tester trybot."
        },
        {
          "count": 3,
          "type": "count",
          "name": "tryjobverifier-start-count",
          "description": "Number of tryjob verifier runs started."
        },
        {
          "count": 0,
          "type": "count",
          "name": "attempt-false-reject-trigger-count",
          "description": "Number of failed job trigger attempts on a committed patch."
        },
        {
          "count": 0,
          "type": "count",
          "name": "trybot-false-reject-count",
          "description": "Number of false rejects across all trybots. This counts any failed runs that also had passing runs on the same patch."
        },
        {
          "count": 0,
          "type": "count",
          "name": "attempt-false-reject-cq-presubmit-count",
          "description": "Number of failed CQ presubmit checks on a committed patch."
        },
        {
          "count": 1,
          "type": "count",
          "name": "tryjobverifier-retry-count",
          "description": "Number of tryjob verifier runs retried."
        },
        {
          "count": 1,
          "type": "count",
          "name": "patchset-reject-count",
          "description": "Number of patchsets rejected by the trybots at least once."
        },
        {
          "count": 2,
          "type": "count",
          "name": "trybot-infra_tester-pass-count",
          "description": "Number of passing runs by the infra_tester trybot."
        },
        {
          "count": 0,
          "type": "count",
          "name": "trybot-infra_tester-false-reject-count",
          "description": "Number of false rejects by the infra_tester trybot. This counts any failed runs that also had passing runs on the same patch."
        },
        {
          "count": 0,
          "type": "count",
          "name": "attempt-false-reject-count",
          "description": "Number of failed attempts on a committed patch that passed presubmit, had all LGTMs and were not manually cancelled."
        },
        {
          "count": 0,
          "type": "count",
          "name": "attempt-false-reject-commit-count",
          "description": "Number of failed commit attempts on a committed patch."
        },
        {
          "count": 0,
          "type": "count",
          "name": "tryjobverifier-error-count",
          "description": "Number of tryjob verifier runs errored."
        },
        {
          "count": 1,
          "type": "count",
          "name": "tryjobverifier-fail-count",
          "description": "Number of tryjob verifier runs failed."
        },
        {
          "count": 0,
          "type": "count",
          "name": "tryjobverifier-timeout-count",
          "description": "Number of tryjob verifier runs that timed out."
        },
        {
          "count": 0,
          "type": "count",
          "name": "attempt-false-reject-tryjob-count",
          "description": "Number of failed job attempts on a committed patch."
        },
        {
          "count": 1,
          "type": "count",
          "name": "trybot-fail-count",
          "description": "Number of failing runs across all trybots."
        },
        {
          "count": 2,
          "type": "count",
          "name": "issue-count",
          "description": "Number of issues processed by the CQ."
        },
        {
          "count": 3,
          "type": "count",
          "name": "attempt-count",
          "description": "Number of CQ attempts made."
        },
        {
          "description": "Time spent per committed patchset blocked on a closed tree.",
          "percentile_50": 0,
          "min": 0,
          "max": 0,
          "percentile_90": 0,
          "sample_size": 2,
          "percentile_25": 0,
          "percentile_95": 0,
          "mean": 0,
          "percentile_75": 0,
          "percentile_10": 0,
          "percentile_99": 0,
          "type": "list",
          "unit": "seconds",
          "name": "blocked-on-closed-tree-durations"
        },
        {
          "description": "Time taken by the CQ to land a patch after passing all checks.",
          "percentile_50": 5.4404699999999995,
          "min": 5.02505,
          "max": 5.85589,
          "percentile_90": 5.772806,
          "sample_size": 2,
          "percentile_25": 5.23276,
          "percentile_95": 5.814348,
          "mean": 5.4404699999999995,
          "percentile_75": 5.64818,
          "percentile_10": 5.108134,
          "percentile_99": 5.847581599999999,
          "type": "list",
          "unit": "seconds",
          "name": "patchset-commit-durations"
        },
        {
          "description": "Time spent on each tryjob verifier retry.",
          "percentile_50": 197.59681,
          "min": 197.59681,
          "max": 197.59681,
          "percentile_90": 197.59681,
          "sample_size": 1,
          "percentile_25": 197.59681,
          "percentile_95": 197.59681,
          "mean": 197.59681,
          "percentile_75": 197.59681,
          "percentile_10": 197.59681,
          "percentile_99": 197.59681,
          "type": "list",
          "unit": "seconds",
          "name": "tryjobverifier-retry-durations"
        },
        {
          "description": "Time spent per committed patchset blocked on a throttled tree.",
          "percentile_50": 0,
          "min": 0,
          "max": 0,
          "percentile_90": 0,
          "sample_size": 2,
          "percentile_25": 0,
          "percentile_95": 0,
          "mean": 0,
          "percentile_75": 0,
          "percentile_10": 0,
          "percentile_99": 0,
          "type": "list",
          "unit": "seconds",
          "name": "blocked-on-throttled-tree-durations"
        },
        {
          "description": "Total time spent in the CQ per patchset, counts multiple CQ attempts as one.",
          "percentile_50": 221.66323,
          "min": 220.97879,
          "max": 385.26816,
          "percentile_90": 352.54717400000004,
          "sample_size": 3,
          "percentile_25": 221.32101,
          "percentile_95": 368.907667,
          "mean": 275.97006000000005,
          "percentile_75": 303.465695,
          "percentile_10": 221.11567800000003,
          "percentile_99": 381.99606140000003,
          "type": "list",
          "unit": "seconds",
          "name": "patchset-durations"
        },
        {
          "description": "Total time spent in the CQ per patch.",
          "percentile_50": 221.66323,
          "min": 220.97879,
          "max": 385.26816,
          "percentile_90": 352.54717400000004,
          "sample_size": 3,
          "percentile_25": 221.32101,
          "percentile_95": 368.907667,
          "mean": 275.97006000000005,
          "percentile_75": 303.465695,
          "percentile_10": 221.11567800000003,
          "percentile_99": 381.99606140000003,
          "type": "list",
          "unit": "seconds",
          "name": "patchset-total-commit-queue-durations"
        },
        {
          "description": "Total time spent per CQ attempt on tryjob verifier runs.",
          "percentile_50": 209.85367,
          "min": 208.81467,
          "max": 380.66758,
          "percentile_90": 346.504798,
          "sample_size": 3,
          "percentile_25": 209.33417,
          "percentile_95": 363.58618899999993,
          "mean": 266.4453066666667,
          "percentile_75": 295.260625,
          "percentile_10": 209.02247,
          "percentile_99": 377.2513018,
          "type": "list",
          "unit": "seconds",
          "name": "tryjobverifier-total-durations"
        },
        {
          "description": "Total time spent per CQ attempt.",
          "percentile_50": 221.66323,
          "min": 220.97879,
          "max": 385.26816,
          "percentile_90": 352.54717400000004,
          "sample_size": 3,
          "percentile_25": 221.32101,
          "percentile_95": 368.907667,
          "mean": 275.97006000000005,
          "percentile_75": 303.465695,
          "percentile_10": 221.11567800000003,
          "percentile_99": 381.99606140000003,
          "type": "list",
          "unit": "seconds",
          "name": "attempt-durations"
        },
        {
          "description": "Time spent on each tryjob verifier first run.",
          "percentile_50": 208.81467,
          "min": 183.07077,
          "max": 209.85367,
          "percentile_90": 209.64587,
          "sample_size": 3,
          "percentile_25": 195.94272,
          "percentile_95": 209.74976999999998,
          "mean": 200.57970333333333,
          "percentile_75": 209.33417,
          "percentile_10": 188.21955000000003,
          "percentile_99": 209.83289,
          "type": "list",
          "unit": "seconds",
          "name": "tryjobverifier-first-run-durations"
        },
        {
          "description": "Number of CQ attempts per patchset.",
          "percentile_50": 1,
          "min": 1,
          "max": 1,
          "percentile_90": 1,
          "sample_size": 3,
          "percentile_25": 1,
          "percentile_95": 1,
          "mean": 1,
          "percentile_75": 1,
          "percentile_10": 1,
          "percentile_99": 1,
          "type": "list",
          "unit": "attempts",
          "name": "patchset-attempts"
        },
        {
          "description": "Total time per patch since their commit box was checked.",
          "percentile_50": 221.66323,
          "min": 220.97879,
          "max": 385.26816,
          "percentile_90": 352.54717400000004,
          "sample_size": 3,
          "percentile_25": 221.32101,
          "percentile_95": 368.907667,
          "mean": 275.97006000000005,
          "percentile_75": 303.465695,
          "percentile_10": 221.11567800000003,
          "percentile_99": 381.99606140000003,
          "type": "list",
          "unit": "seconds",
          "name": "patchset-total-wall-time-durations"
        }
      ]
    },
    {
      "begin": 1434142800,
      "end": 1434146400,
      "interval_minutes": 60,
      "project": "infra",
      "key": 4854631502970880,
      "stats": [
        {
          "count": 1,
          "type": "count",
          "name": "tryjobverifier-skip-count",
          "description": "Number of tryjob verifier runs skipped."
        },
        {
          "count": 3,
          "type": "count",
          "name": "patchset-count",
          "description": "Number of patchsets processed by the CQ."
        },
        {
          "count": 3,
          "type": "count",
          "name": "patchset-commit-count",
          "description": "Number of patchsets committed by the CQ."
        },
        {
          "count": 2,
          "type": "count",
          "name": "tryjobverifier-pass-count",
          "description": "Number of tryjob verifier runs passed."
        },
        {
          "count": 0,
          "type": "count",
          "name": "patchset-false-reject-count",
          "description": "Number of patchsets rejected by the trybots that eventually passed."
        },
        {
          "count": 2,
          "type": "count",
          "name": "trybot-pass-count",
          "description": "Number of passing runs across all trybots."
        },
        {
          "count": 0,
          "type": "count",
          "name": "trybot-infra_tester-fail-count",
          "description": "Number of failing runs by the infra_tester trybot."
        },
        {
          "count": 2,
          "type": "count",
          "name": "tryjobverifier-start-count",
          "description": "Number of tryjob verifier runs started."
        },
        {
          "count": 0,
          "type": "count",
          "name": "attempt-false-reject-trigger-count",
          "description": "Number of failed job trigger attempts on a committed patch."
        },
        {
          "count": 0,
          "type": "count",
          "name": "trybot-false-reject-count",
          "description": "Number of false rejects across all trybots. This counts any failed runs that also had passing runs on the same patch."
        },
        {
          "count": 0,
          "type": "count",
          "name": "attempt-false-reject-cq-presubmit-count",
          "description": "Number of failed CQ presubmit checks on a committed patch."
        },
        {
          "count": 0,
          "type": "count",
          "name": "tryjobverifier-retry-count",
          "description": "Number of tryjob verifier runs retried."
        },
        {
          "count": 0,
          "type": "count",
          "name": "patchset-reject-count",
          "description": "Number of patchsets rejected by the trybots at least once."
        },
        {
          "count": 2,
          "type": "count",
          "name": "trybot-infra_tester-pass-count",
          "description": "Number of passing runs by the infra_tester trybot."
        },
        {
          "count": 0,
          "type": "count",
          "name": "trybot-infra_tester-false-reject-count",
          "description": "Number of false rejects by the infra_tester trybot. This counts any failed runs that also had passing runs on the same patch."
        },
        {
          "count": 0,
          "type": "count",
          "name": "attempt-false-reject-count",
          "description": "Number of failed attempts on a committed patch that passed presubmit, had all LGTMs and were not manually cancelled."
        },
        {
          "count": 0,
          "type": "count",
          "name": "attempt-false-reject-commit-count",
          "description": "Number of failed commit attempts on a committed patch."
        },
        {
          "count": 0,
          "type": "count",
          "name": "tryjobverifier-error-count",
          "description": "Number of tryjob verifier runs errored."
        },
        {
          "count": 0,
          "type": "count",
          "name": "tryjobverifier-fail-count",
          "description": "Number of tryjob verifier runs failed."
        },
        {
          "count": 0,
          "type": "count",
          "name": "tryjobverifier-timeout-count",
          "description": "Number of tryjob verifier runs that timed out."
        },
        {
          "count": 0,
          "type": "count",
          "name": "attempt-false-reject-tryjob-count",
          "description": "Number of failed job attempts on a committed patch."
        },
        {
          "count": 0,
          "type": "count",
          "name": "trybot-fail-count",
          "description": "Number of failing runs across all trybots."
        },
        {
          "count": 3,
          "type": "count",
          "name": "issue-count",
          "description": "Number of issues processed by the CQ."
        },
        {
          "count": 3,
          "type": "count",
          "name": "attempt-count",
          "description": "Number of CQ attempts made."
        },
        {
          "description": "Time spent per committed patchset blocked on a closed tree.",
          "percentile_50": 0,
          "min": 0,
          "max": 0,
          "percentile_90": 0,
          "sample_size": 3,
          "percentile_25": 0,
          "percentile_95": 0,
          "mean": 0,
          "percentile_75": 0,
          "percentile_10": 0,
          "percentile_99": 0,
          "type": "list",
          "unit": "seconds",
          "name": "blocked-on-closed-tree-durations"
        },
        {
          "description": "Time taken by the CQ to land a patch after passing all checks.",
          "percentile_50": 3.26568,
          "min": 3.19668,
          "max": 4.0898,
          "percentile_90": 3.9249760000000005,
          "sample_size": 3,
          "percentile_25": 3.23118,
          "percentile_95": 4.007388,
          "mean": 3.517386666666667,
          "percentile_75": 3.67774,
          "percentile_10": 3.2104800000000004,
          "percentile_99": 4.0733176,
          "type": "list",
          "unit": "seconds",
          "name": "patchset-commit-durations"
        },
        {
          "description": "Time spent on each tryjob verifier retry.",
          "percentile_50": 0,
          "min": 0,
          "max": 0,
          "percentile_90": 0,
          "sample_size": 0,
          "percentile_25": 0,
          "percentile_95": 0,
          "mean": 0,
          "percentile_75": 0,
          "percentile_10": 0,
          "percentile_99": 0,
          "type": "list",
          "unit": "seconds",
          "name": "tryjobverifier-retry-durations"
        },
        {
          "description": "Time spent per committed patchset blocked on a throttled tree.",
          "percentile_50": 0,
          "min": 0,
          "max": 0,
          "percentile_90": 0,
          "sample_size": 3,
          "percentile_25": 0,
          "percentile_95": 0,
          "mean": 0,
          "percentile_75": 0,
          "percentile_10": 0,
          "percentile_99": 0,
          "type": "list",
          "unit": "seconds",
          "name": "blocked-on-throttled-tree-durations"
        },
        {
          "description": "Total time spent in the CQ per patchset, counts multiple CQ attempts as one.",
          "percentile_50": 194.98331,
          "min": 9.20691,
          "max": 217.60494,
          "percentile_90": 213.080614,
          "sample_size": 3,
          "percentile_25": 102.09510999999999,
          "percentile_95": 215.34277699999998,
          "mean": 140.59838666666667,
          "percentile_75": 206.294125,
          "percentile_10": 46.36219,
          "percentile_99": 217.15250740000002,
          "type": "list",
          "unit": "seconds",
          "name": "patchset-durations"
        },
        {
          "description": "Total time spent in the CQ per patch.",
          "percentile_50": 194.98331,
          "min": 9.20691,
          "max": 217.60494,
          "percentile_90": 213.080614,
          "sample_size": 3,
          "percentile_25": 102.09510999999999,
          "percentile_95": 215.34277699999998,
          "mean": 140.59838666666667,
          "percentile_75": 206.294125,
          "percentile_10": 46.36219,
          "percentile_99": 217.15250740000002,
          "type": "list",
          "unit": "seconds",
          "name": "patchset-total-commit-queue-durations"
        },
        {
          "description": "Total time spent per CQ attempt on tryjob verifier runs.",
          "percentile_50": 184.93013,
          "min": 0.05456,
          "max": 206.82086,
          "percentile_90": 202.442714,
          "sample_size": 3,
          "percentile_25": 92.492345,
          "percentile_95": 204.631787,
          "mean": 130.60185,
          "percentile_75": 195.875495,
          "percentile_10": 37.029674,
          "percentile_99": 206.38304540000001,
          "type": "list",
          "unit": "seconds",
          "name": "tryjobverifier-total-durations"
        },
        {
          "description": "Total time spent per CQ attempt.",
          "percentile_50": 194.98331,
          "min": 9.20691,
          "max": 217.60494,
          "percentile_90": 213.080614,
          "sample_size": 3,
          "percentile_25": 102.09510999999999,
          "percentile_95": 215.34277699999998,
          "mean": 140.59838666666667,
          "percentile_75": 206.294125,
          "percentile_10": 46.36219,
          "percentile_99": 217.15250740000002,
          "type": "list",
          "unit": "seconds",
          "name": "attempt-durations"
        },
        {
          "description": "Time spent on each tryjob verifier first run.",
          "percentile_50": 195.875495,
          "min": 184.93013,
          "max": 206.82086,
          "percentile_90": 204.631787,
          "sample_size": 2,
          "percentile_25": 190.4028125,
          "percentile_95": 205.7263235,
          "mean": 195.875495,
          "percentile_75": 201.3481775,
          "percentile_10": 187.119203,
          "percentile_99": 206.60195270000003,
          "type": "list",
          "unit": "seconds",
          "name": "tryjobverifier-first-run-durations"
        },
        {
          "description": "Number of CQ attempts per patchset.",
          "percentile_50": 1,
          "min": 1,
          "max": 1,
          "percentile_90": 1,
          "sample_size": 3,
          "percentile_25": 1,
          "percentile_95": 1,
          "mean": 1,
          "percentile_75": 1,
          "percentile_10": 1,
          "percentile_99": 1,
          "type": "list",
          "unit": "attempts",
          "name": "patchset-attempts"
        },
        {
          "description": "Total time per patch since their commit box was checked.",
          "percentile_50": 194.98331,
          "min": 9.20691,
          "max": 217.60494,
          "percentile_90": 213.080614,
          "sample_size": 3,
          "percentile_25": 102.09510999999999,
          "percentile_95": 215.34277699999998,
          "mean": 140.59838666666667,
          "percentile_75": 206.294125,
          "percentile_10": 46.36219,
          "percentile_99": 217.15250740000002,
          "type": "list",
          "unit": "seconds",
          "name": "patchset-total-wall-time-durations"
        }
      ]
    },
    {
      "begin": 1434139200,
      "end": 1434142800,
      "interval_minutes": 60,
      "project": "infra",
      "key": 6308229562761216,
      "stats": [
        {
          "count": 0,
          "type": "count",
          "name": "tryjobverifier-skip-count",
          "description": "Number of tryjob verifier runs skipped."
        },
        {
          "count": 1,
          "type": "count",
          "name": "patchset-count",
          "description": "Number of patchsets processed by the CQ."
        },
        {
          "count": 1,
          "type": "count",
          "name": "patchset-commit-count",
          "description": "Number of patchsets committed by the CQ."
        },
        {
          "count": 1,
          "type": "count",
          "name": "tryjobverifier-pass-count",
          "description": "Number of tryjob verifier runs passed."
        },
        {
          "count": 0,
          "type": "count",
          "name": "patchset-false-reject-count",
          "description": "Number of patchsets rejected by the trybots that eventually passed."
        },
        {
          "count": 1,
          "type": "count",
          "name": "trybot-pass-count",
          "description": "Number of passing runs across all trybots."
        },
        {
          "count": 0,
          "type": "count",
          "name": "trybot-infra_tester-fail-count",
          "description": "Number of failing runs by the infra_tester trybot."
        },
        {
          "count": 1,
          "type": "count",
          "name": "tryjobverifier-start-count",
          "description": "Number of tryjob verifier runs started."
        },
        {
          "count": 0,
          "type": "count",
          "name": "attempt-false-reject-trigger-count",
          "description": "Number of failed job trigger attempts on a committed patch."
        },
        {
          "count": 0,
          "type": "count",
          "name": "trybot-false-reject-count",
          "description": "Number of false rejects across all trybots. This counts any failed runs that also had passing runs on the same patch."
        },
        {
          "count": 0,
          "type": "count",
          "name": "attempt-false-reject-cq-presubmit-count",
          "description": "Number of failed CQ presubmit checks on a committed patch."
        },
        {
          "count": 0,
          "type": "count",
          "name": "tryjobverifier-retry-count",
          "description": "Number of tryjob verifier runs retried."
        },
        {
          "count": 0,
          "type": "count",
          "name": "patchset-reject-count",
          "description": "Number of patchsets rejected by the trybots at least once."
        },
        {
          "count": 1,
          "type": "count",
          "name": "trybot-infra_tester-pass-count",
          "description": "Number of passing runs by the infra_tester trybot."
        },
        {
          "count": 0,
          "type": "count",
          "name": "trybot-infra_tester-false-reject-count",
          "description": "Number of false rejects by the infra_tester trybot. This counts any failed runs that also had passing runs on the same patch."
        },
        {
          "count": 0,
          "type": "count",
          "name": "attempt-false-reject-count",
          "description": "Number of failed attempts on a committed patch that passed presubmit, had all LGTMs and were not manually cancelled."
        },
        {
          "count": 0,
          "type": "count",
          "name": "attempt-false-reject-commit-count",
          "description": "Number of failed commit attempts on a committed patch."
        },
        {
          "count": 0,
          "type": "count",
          "name": "tryjobverifier-error-count",
          "description": "Number of tryjob verifier runs errored."
        },
        {
          "count": 0,
          "type": "count",
          "name": "tryjobverifier-fail-count",
          "description": "Number of tryjob verifier runs failed."
        },
        {
          "count": 0,
          "type": "count",
          "name": "tryjobverifier-timeout-count",
          "description": "Number of tryjob verifier runs that timed out."
        },
        {
          "count": 0,
          "type": "count",
          "name": "attempt-false-reject-tryjob-count",
          "description": "Number of failed job attempts on a committed patch."
        },
        {
          "count": 0,
          "type": "count",
          "name": "trybot-fail-count",
          "description": "Number of failing runs across all trybots."
        },
        {
          "count": 1,
          "type": "count",
          "name": "issue-count",
          "description": "Number of issues processed by the CQ."
        },
        {
          "count": 1,
          "type": "count",
          "name": "attempt-count",
          "description": "Number of CQ attempts made."
        },
        {
          "description": "Time spent per committed patchset blocked on a closed tree.",
          "percentile_50": 0,
          "min": 0,
          "max": 0,
          "percentile_90": 0,
          "sample_size": 1,
          "percentile_25": 0,
          "percentile_95": 0,
          "mean": 0,
          "percentile_75": 0,
          "percentile_10": 0,
          "percentile_99": 0,
          "type": "list",
          "unit": "seconds",
          "name": "blocked-on-closed-tree-durations"
        },
        {
          "description": "Time taken by the CQ to land a patch after passing all checks.",
          "percentile_50": 2.97648,
          "min": 2.97648,
          "max": 2.97648,
          "percentile_90": 2.97648,
          "sample_size": 1,
          "percentile_25": 2.97648,
          "percentile_95": 2.97648,
          "mean": 2.97648,
          "percentile_75": 2.97648,
          "percentile_10": 2.97648,
          "percentile_99": 2.97648,
          "type": "list",
          "unit": "seconds",
          "name": "patchset-commit-durations"
        },
        {
          "description": "Time spent on each tryjob verifier retry.",
          "percentile_50": 0,
          "min": 0,
          "max": 0,
          "percentile_90": 0,
          "sample_size": 0,
          "percentile_25": 0,
          "percentile_95": 0,
          "mean": 0,
          "percentile_75": 0,
          "percentile_10": 0,
          "percentile_99": 0,
          "type": "list",
          "unit": "seconds",
          "name": "tryjobverifier-retry-durations"
        },
        {
          "description": "Time spent per committed patchset blocked on a throttled tree.",
          "percentile_50": 0,
          "min": 0,
          "max": 0,
          "percentile_90": 0,
          "sample_size": 1,
          "percentile_25": 0,
          "percentile_95": 0,
          "mean": 0,
          "percentile_75": 0,
          "percentile_10": 0,
          "percentile_99": 0,
          "type": "list",
          "unit": "seconds",
          "name": "blocked-on-throttled-tree-durations"
        },
        {
          "description": "Total time spent in the CQ per patchset, counts multiple CQ attempts as one.",
          "percentile_50": 473.01608,
          "min": 473.01608,
          "max": 473.01608,
          "percentile_90": 473.01608,
          "sample_size": 1,
          "percentile_25": 473.01608,
          "percentile_95": 473.01608,
          "mean": 473.01608,
          "percentile_75": 473.01608,
          "percentile_10": 473.01608,
          "percentile_99": 473.01608,
          "type": "list",
          "unit": "seconds",
          "name": "patchset-durations"
        },
        {
          "description": "Total time spent in the CQ per patch.",
          "percentile_50": 473.01608,
          "min": 473.01608,
          "max": 473.01608,
          "percentile_90": 473.01608,
          "sample_size": 1,
          "percentile_25": 473.01608,
          "percentile_95": 473.01608,
          "mean": 473.01608,
          "percentile_75": 473.01608,
          "percentile_10": 473.01608,
          "percentile_99": 473.01608,
          "type": "list",
          "unit": "seconds",
          "name": "patchset-total-commit-queue-durations"
        },
        {
          "description": "Total time spent per CQ attempt on tryjob verifier runs.",
          "percentile_50": 465.62457,
          "min": 465.62457,
          "max": 465.62457,
          "percentile_90": 465.62457,
          "sample_size": 1,
          "percentile_25": 465.62457,
          "percentile_95": 465.62457,
          "mean": 465.62457,
          "percentile_75": 465.62457,
          "percentile_10": 465.62457,
          "percentile_99": 465.62457,
          "type": "list",
          "unit": "seconds",
          "name": "tryjobverifier-total-durations"
        },
        {
          "description": "Total time spent per CQ attempt.",
          "percentile_50": 473.01608,
          "min": 473.01608,
          "max": 473.01608,
          "percentile_90": 473.01608,
          "sample_size": 1,
          "percentile_25": 473.01608,
          "percentile_95": 473.01608,
          "mean": 473.01608,
          "percentile_75": 473.01608,
          "percentile_10": 473.01608,
          "percentile_99": 473.01608,
          "type": "list",
          "unit": "seconds",
          "name": "attempt-durations"
        },
        {
          "description": "Time spent on each tryjob verifier first run.",
          "percentile_50": 465.62457,
          "min": 465.62457,
          "max": 465.62457,
          "percentile_90": 465.62457,
          "sample_size": 1,
          "percentile_25": 465.62457,
          "percentile_95": 465.62457,
          "mean": 465.62457,
          "percentile_75": 465.62457,
          "percentile_10": 465.62457,
          "percentile_99": 465.62457,
          "type": "list",
          "unit": "seconds",
          "name": "tryjobverifier-first-run-durations"
        },
        {
          "description": "Number of CQ attempts per patchset.",
          "percentile_50": 1,
          "min": 1,
          "max": 1,
          "percentile_90": 1,
          "sample_size": 1,
          "percentile_25": 1,
          "percentile_95": 1,
          "mean": 1,
          "percentile_75": 1,
          "percentile_10": 1,
          "percentile_99": 1,
          "type": "list",
          "unit": "attempts",
          "name": "patchset-attempts"
        },
        {
          "description": "Total time per patch since their commit box was checked.",
          "percentile_50": 473.01608,
          "min": 473.01608,
          "max": 473.01608,
          "percentile_90": 473.01608,
          "sample_size": 1,
          "percentile_25": 473.01608,
          "percentile_95": 473.01608,
          "mean": 473.01608,
          "percentile_75": 473.01608,
          "percentile_10": 473.01608,
          "percentile_99": 473.01608,
          "type": "list",
          "unit": "seconds",
          "name": "patchset-total-wall-time-durations"
        }
      ]
    },
    {
      "begin": 1434132000,
      "end": 1434135600,
      "interval_minutes": 60,
      "project": "infra",
      "key": 5632176477437952,
      "stats": [
        {
          "count": 0,
          "type": "count",
          "name": "tryjobverifier-skip-count",
          "description": "Number of tryjob verifier runs skipped."
        },
        {
          "count": 1,
          "type": "count",
          "name": "patchset-count",
          "description": "Number of patchsets processed by the CQ."
        },
        {
          "count": 1,
          "type": "count",
          "name": "patchset-commit-count",
          "description": "Number of patchsets committed by the CQ."
        },
        {
          "count": 1,
          "type": "count",
          "name": "tryjobverifier-pass-count",
          "description": "Number of tryjob verifier runs passed."
        },
        {
          "count": 0,
          "type": "count",
          "name": "patchset-false-reject-count",
          "description": "Number of patchsets rejected by the trybots that eventually passed."
        },
        {
          "count": 1,
          "type": "count",
          "name": "trybot-pass-count",
          "description": "Number of passing runs across all trybots."
        },
        {
          "count": 0,
          "type": "count",
          "name": "trybot-infra_tester-fail-count",
          "description": "Number of failing runs by the infra_tester trybot."
        },
        {
          "count": 1,
          "type": "count",
          "name": "tryjobverifier-start-count",
          "description": "Number of tryjob verifier runs started."
        },
        {
          "count": 0,
          "type": "count",
          "name": "attempt-false-reject-trigger-count",
          "description": "Number of failed job trigger attempts on a committed patch."
        },
        {
          "count": 0,
          "type": "count",
          "name": "trybot-false-reject-count",
          "description": "Number of false rejects across all trybots. This counts any failed runs that also had passing runs on the same patch."
        },
        {
          "count": 0,
          "type": "count",
          "name": "attempt-false-reject-cq-presubmit-count",
          "description": "Number of failed CQ presubmit checks on a committed patch."
        },
        {
          "count": 0,
          "type": "count",
          "name": "tryjobverifier-retry-count",
          "description": "Number of tryjob verifier runs retried."
        },
        {
          "count": 0,
          "type": "count",
          "name": "patchset-reject-count",
          "description": "Number of patchsets rejected by the trybots at least once."
        },
        {
          "count": 1,
          "type": "count",
          "name": "trybot-infra_tester-pass-count",
          "description": "Number of passing runs by the infra_tester trybot."
        },
        {
          "count": 0,
          "type": "count",
          "name": "trybot-infra_tester-false-reject-count",
          "description": "Number of false rejects by the infra_tester trybot. This counts any failed runs that also had passing runs on the same patch."
        },
        {
          "count": 0,
          "type": "count",
          "name": "attempt-false-reject-count",
          "description": "Number of failed attempts on a committed patch that passed presubmit, had all LGTMs and were not manually cancelled."
        },
        {
          "count": 0,
          "type": "count",
          "name": "attempt-false-reject-commit-count",
          "description": "Number of failed commit attempts on a committed patch."
        },
        {
          "count": 0,
          "type": "count",
          "name": "tryjobverifier-error-count",
          "description": "Number of tryjob verifier runs errored."
        },
        {
          "count": 0,
          "type": "count",
          "name": "tryjobverifier-fail-count",
          "description": "Number of tryjob verifier runs failed."
        },
        {
          "count": 0,
          "type": "count",
          "name": "tryjobverifier-timeout-count",
          "description": "Number of tryjob verifier runs that timed out."
        },
        {
          "count": 0,
          "type": "count",
          "name": "attempt-false-reject-tryjob-count",
          "description": "Number of failed job attempts on a committed patch."
        },
        {
          "count": 0,
          "type": "count",
          "name": "trybot-fail-count",
          "description": "Number of failing runs across all trybots."
        },
        {
          "count": 1,
          "type": "count",
          "name": "issue-count",
          "description": "Number of issues processed by the CQ."
        },
        {
          "count": 1,
          "type": "count",
          "name": "attempt-count",
          "description": "Number of CQ attempts made."
        },
        {
          "description": "Time spent per committed patchset blocked on a closed tree.",
          "percentile_50": 0,
          "min": 0,
          "max": 0,
          "percentile_90": 0,
          "sample_size": 1,
          "percentile_25": 0,
          "percentile_95": 0,
          "mean": 0,
          "percentile_75": 0,
          "percentile_10": 0,
          "percentile_99": 0,
          "type": "list",
          "unit": "seconds",
          "name": "blocked-on-closed-tree-durations"
        },
        {
          "description": "Time taken by the CQ to land a patch after passing all checks.",
          "percentile_50": 3.25917,
          "min": 3.25917,
          "max": 3.25917,
          "percentile_90": 3.25917,
          "sample_size": 1,
          "percentile_25": 3.25917,
          "percentile_95": 3.25917,
          "mean": 3.25917,
          "percentile_75": 3.25917,
          "percentile_10": 3.25917,
          "percentile_99": 3.25917,
          "type": "list",
          "unit": "seconds",
          "name": "patchset-commit-durations"
        },
        {
          "description": "Time spent on each tryjob verifier retry.",
          "percentile_50": 0,
          "min": 0,
          "max": 0,
          "percentile_90": 0,
          "sample_size": 0,
          "percentile_25": 0,
          "percentile_95": 0,
          "mean": 0,
          "percentile_75": 0,
          "percentile_10": 0,
          "percentile_99": 0,
          "type": "list",
          "unit": "seconds",
          "name": "tryjobverifier-retry-durations"
        },
        {
          "description": "Time spent per committed patchset blocked on a throttled tree.",
          "percentile_50": 0,
          "min": 0,
          "max": 0,
          "percentile_90": 0,
          "sample_size": 1,
          "percentile_25": 0,
          "percentile_95": 0,
          "mean": 0,
          "percentile_75": 0,
          "percentile_10": 0,
          "percentile_99": 0,
          "type": "list",
          "unit": "seconds",
          "name": "blocked-on-throttled-tree-durations"
        },
        {
          "description": "Total time spent in the CQ per patchset, counts multiple CQ attempts as one.",
          "percentile_50": 245.63969,
          "min": 245.63969,
          "max": 245.63969,
          "percentile_90": 245.63969,
          "sample_size": 1,
          "percentile_25": 245.63969,
          "percentile_95": 245.63969,
          "mean": 245.63969,
          "percentile_75": 245.63969,
          "percentile_10": 245.63969,
          "percentile_99": 245.63969,
          "type": "list",
          "unit": "seconds",
          "name": "patchset-durations"
        },
        {
          "description": "Total time spent in the CQ per patch.",
          "percentile_50": 245.63969,
          "min": 245.63969,
          "max": 245.63969,
          "percentile_90": 245.63969,
          "sample_size": 1,
          "percentile_25": 245.63969,
          "percentile_95": 245.63969,
          "mean": 245.63969,
          "percentile_75": 245.63969,
          "percentile_10": 245.63969,
          "percentile_99": 245.63969,
          "type": "list",
          "unit": "seconds",
          "name": "patchset-total-commit-queue-durations"
        },
        {
          "description": "Total time spent per CQ attempt on tryjob verifier runs.",
          "percentile_50": 234.9721,
          "min": 234.9721,
          "max": 234.9721,
          "percentile_90": 234.9721,
          "sample_size": 1,
          "percentile_25": 234.9721,
          "percentile_95": 234.9721,
          "mean": 234.9721,
          "percentile_75": 234.9721,
          "percentile_10": 234.9721,
          "percentile_99": 234.9721,
          "type": "list",
          "unit": "seconds",
          "name": "tryjobverifier-total-durations"
        },
        {
          "description": "Total time spent per CQ attempt.",
          "percentile_50": 245.63969,
          "min": 245.63969,
          "max": 245.63969,
          "percentile_90": 245.63969,
          "sample_size": 1,
          "percentile_25": 245.63969,
          "percentile_95": 245.63969,
          "mean": 245.63969,
          "percentile_75": 245.63969,
          "percentile_10": 245.63969,
          "percentile_99": 245.63969,
          "type": "list",
          "unit": "seconds",
          "name": "attempt-durations"
        },
        {
          "description": "Time spent on each tryjob verifier first run.",
          "percentile_50": 234.9721,
          "min": 234.9721,
          "max": 234.9721,
          "percentile_90": 234.9721,
          "sample_size": 1,
          "percentile_25": 234.9721,
          "percentile_95": 234.9721,
          "mean": 234.9721,
          "percentile_75": 234.9721,
          "percentile_10": 234.9721,
          "percentile_99": 234.9721,
          "type": "list",
          "unit": "seconds",
          "name": "tryjobverifier-first-run-durations"
        },
        {
          "description": "Number of CQ attempts per patchset.",
          "percentile_50": 1,
          "min": 1,
          "max": 1,
          "percentile_90": 1,
          "sample_size": 1,
          "percentile_25": 1,
          "percentile_95": 1,
          "mean": 1,
          "percentile_75": 1,
          "percentile_10": 1,
          "percentile_99": 1,
          "type": "list",
          "unit": "attempts",
          "name": "patchset-attempts"
        },
        {
          "description": "Total time per patch since their commit box was checked.",
          "percentile_50": 245.63969,
          "min": 245.63969,
          "max": 245.63969,
          "percentile_90": 245.63969,
          "sample_size": 1,
          "percentile_25": 245.63969,
          "percentile_95": 245.63969,
          "mean": 245.63969,
          "percentile_75": 245.63969,
          "percentile_10": 245.63969,
          "percentile_99": 245.63969,
          "type": "list",
          "unit": "seconds",
          "name": "patchset-total-wall-time-durations"
        }
      ]
    },
    {
      "begin": 1434128400,
      "end": 1434132000,
      "interval_minutes": 60,
      "project": "infra",
      "key": 5136106479681536,
      "stats": [
        {
          "count": 0,
          "type": "count",
          "name": "tryjobverifier-skip-count",
          "description": "Number of tryjob verifier runs skipped."
        },
        {
          "count": 1,
          "type": "count",
          "name": "patchset-count",
          "description": "Number of patchsets processed by the CQ."
        },
        {
          "count": 1,
          "type": "count",
          "name": "patchset-commit-count",
          "description": "Number of patchsets committed by the CQ."
        },
        {
          "count": 1,
          "type": "count",
          "name": "tryjobverifier-pass-count",
          "description": "Number of tryjob verifier runs passed."
        },
        {
          "count": 0,
          "type": "count",
          "name": "patchset-false-reject-count",
          "description": "Number of patchsets rejected by the trybots that eventually passed."
        },
        {
          "count": 1,
          "type": "count",
          "name": "trybot-pass-count",
          "description": "Number of passing runs across all trybots."
        },
        {
          "count": 0,
          "type": "count",
          "name": "trybot-infra_tester-fail-count",
          "description": "Number of failing runs by the infra_tester trybot."
        },
        {
          "count": 1,
          "type": "count",
          "name": "tryjobverifier-start-count",
          "description": "Number of tryjob verifier runs started."
        },
        {
          "count": 0,
          "type": "count",
          "name": "attempt-false-reject-trigger-count",
          "description": "Number of failed job trigger attempts on a committed patch."
        },
        {
          "count": 0,
          "type": "count",
          "name": "trybot-false-reject-count",
          "description": "Number of false rejects across all trybots. This counts any failed runs that also had passing runs on the same patch."
        },
        {
          "count": 0,
          "type": "count",
          "name": "attempt-false-reject-cq-presubmit-count",
          "description": "Number of failed CQ presubmit checks on a committed patch."
        },
        {
          "count": 0,
          "type": "count",
          "name": "tryjobverifier-retry-count",
          "description": "Number of tryjob verifier runs retried."
        },
        {
          "count": 0,
          "type": "count",
          "name": "patchset-reject-count",
          "description": "Number of patchsets rejected by the trybots at least once."
        },
        {
          "count": 1,
          "type": "count",
          "name": "trybot-infra_tester-pass-count",
          "description": "Number of passing runs by the infra_tester trybot."
        },
        {
          "count": 0,
          "type": "count",
          "name": "trybot-infra_tester-false-reject-count",
          "description": "Number of false rejects by the infra_tester trybot. This counts any failed runs that also had passing runs on the same patch."
        },
        {
          "count": 0,
          "type": "count",
          "name": "attempt-false-reject-count",
          "description": "Number of failed attempts on a committed patch that passed presubmit, had all LGTMs and were not manually cancelled."
        },
        {
          "count": 0,
          "type": "count",
          "name": "attempt-false-reject-commit-count",
          "description": "Number of failed commit attempts on a committed patch."
        },
        {
          "count": 0,
          "type": "count",
          "name": "tryjobverifier-error-count",
          "description": "Number of tryjob verifier runs errored."
        },
        {
          "count": 0,
          "type": "count",
          "name": "tryjobverifier-fail-count",
          "description": "Number of tryjob verifier runs failed."
        },
        {
          "count": 0,
          "type": "count",
          "name": "tryjobverifier-timeout-count",
          "description": "Number of tryjob verifier runs that timed out."
        },
        {
          "count": 0,
          "type": "count",
          "name": "attempt-false-reject-tryjob-count",
          "description": "Number of failed job attempts on a committed patch."
        },
        {
          "count": 0,
          "type": "count",
          "name": "trybot-fail-count",
          "description": "Number of failing runs across all trybots."
        },
        {
          "count": 1,
          "type": "count",
          "name": "issue-count",
          "description": "Number of issues processed by the CQ."
        },
        {
          "count": 1,
          "type": "count",
          "name": "attempt-count",
          "description": "Number of CQ attempts made."
        },
        {
          "description": "Time spent per committed patchset blocked on a closed tree.",
          "percentile_50": 0,
          "min": 0,
          "max": 0,
          "percentile_90": 0,
          "sample_size": 1,
          "percentile_25": 0,
          "percentile_95": 0,
          "mean": 0,
          "percentile_75": 0,
          "percentile_10": 0,
          "percentile_99": 0,
          "type": "list",
          "unit": "seconds",
          "name": "blocked-on-closed-tree-durations"
        },
        {
          "description": "Time taken by the CQ to land a patch after passing all checks.",
          "percentile_50": 7.47758,
          "min": 7.47758,
          "max": 7.47758,
          "percentile_90": 7.47758,
          "sample_size": 1,
          "percentile_25": 7.47758,
          "percentile_95": 7.47758,
          "mean": 7.47758,
          "percentile_75": 7.47758,
          "percentile_10": 7.47758,
          "percentile_99": 7.47758,
          "type": "list",
          "unit": "seconds",
          "name": "patchset-commit-durations"
        },
        {
          "description": "Time spent on each tryjob verifier retry.",
          "percentile_50": 0,
          "min": 0,
          "max": 0,
          "percentile_90": 0,
          "sample_size": 0,
          "percentile_25": 0,
          "percentile_95": 0,
          "mean": 0,
          "percentile_75": 0,
          "percentile_10": 0,
          "percentile_99": 0,
          "type": "list",
          "unit": "seconds",
          "name": "tryjobverifier-retry-durations"
        },
        {
          "description": "Time spent per committed patchset blocked on a throttled tree.",
          "percentile_50": 0,
          "min": 0,
          "max": 0,
          "percentile_90": 0,
          "sample_size": 1,
          "percentile_25": 0,
          "percentile_95": 0,
          "mean": 0,
          "percentile_75": 0,
          "percentile_10": 0,
          "percentile_99": 0,
          "type": "list",
          "unit": "seconds",
          "name": "blocked-on-throttled-tree-durations"
        },
        {
          "description": "Total time spent in the CQ per patchset, counts multiple CQ attempts as one.",
          "percentile_50": 214.27208,
          "min": 214.27208,
          "max": 214.27208,
          "percentile_90": 214.27208,
          "sample_size": 1,
          "percentile_25": 214.27208,
          "percentile_95": 214.27208,
          "mean": 214.27208,
          "percentile_75": 214.27208,
          "percentile_10": 214.27208,
          "percentile_99": 214.27208,
          "type": "list",
          "unit": "seconds",
          "name": "patchset-durations"
        },
        {
          "description": "Total time spent in the CQ per patch.",
          "percentile_50": 214.27208,
          "min": 214.27208,
          "max": 214.27208,
          "percentile_90": 214.27208,
          "sample_size": 1,
          "percentile_25": 214.27208,
          "percentile_95": 214.27208,
          "mean": 214.27208,
          "percentile_75": 214.27208,
          "percentile_10": 214.27208,
          "percentile_99": 214.27208,
          "type": "list",
          "unit": "seconds",
          "name": "patchset-total-commit-queue-durations"
        },
        {
          "description": "Total time spent per CQ attempt on tryjob verifier runs.",
          "percentile_50": 197.00373,
          "min": 197.00373,
          "max": 197.00373,
          "percentile_90": 197.00373,
          "sample_size": 1,
          "percentile_25": 197.00373,
          "percentile_95": 197.00373,
          "mean": 197.00373,
          "percentile_75": 197.00373,
          "percentile_10": 197.00373,
          "percentile_99": 197.00373,
          "type": "list",
          "unit": "seconds",
          "name": "tryjobverifier-total-durations"
        },
        {
          "description": "Total time spent per CQ attempt.",
          "percentile_50": 214.27208,
          "min": 214.27208,
          "max": 214.27208,
          "percentile_90": 214.27208,
          "sample_size": 1,
          "percentile_25": 214.27208,
          "percentile_95": 214.27208,
          "mean": 214.27208,
          "percentile_75": 214.27208,
          "percentile_10": 214.27208,
          "percentile_99": 214.27208,
          "type": "list",
          "unit": "seconds",
          "name": "attempt-durations"
        },
        {
          "description": "Time spent on each tryjob verifier first run.",
          "percentile_50": 197.00373,
          "min": 197.00373,
          "max": 197.00373,
          "percentile_90": 197.00373,
          "sample_size": 1,
          "percentile_25": 197.00373,
          "percentile_95": 197.00373,
          "mean": 197.00373,
          "percentile_75": 197.00373,
          "percentile_10": 197.00373,
          "percentile_99": 197.00373,
          "type": "list",
          "unit": "seconds",
          "name": "tryjobverifier-first-run-durations"
        },
        {
          "description": "Number of CQ attempts per patchset.",
          "percentile_50": 1,
          "min": 1,
          "max": 1,
          "percentile_90": 1,
          "sample_size": 1,
          "percentile_25": 1,
          "percentile_95": 1,
          "mean": 1,
          "percentile_75": 1,
          "percentile_10": 1,
          "percentile_99": 1,
          "type": "list",
          "unit": "attempts",
          "name": "patchset-attempts"
        },
        {
          "description": "Total time per patch since their commit box was checked.",
          "percentile_50": 214.27208,
          "min": 214.27208,
          "max": 214.27208,
          "percentile_90": 214.27208,
          "sample_size": 1,
          "percentile_25": 214.27208,
          "percentile_95": 214.27208,
          "mean": 214.27208,
          "percentile_75": 214.27208,
          "percentile_10": 214.27208,
          "percentile_99": 214.27208,
          "type": "list",
          "unit": "seconds",
          "name": "patchset-total-wall-time-durations"
        }
      ]
    },
    {
      "begin": 1434067200,
      "end": 1434070800,
      "interval_minutes": 60,
      "project": "infra",
      "key": 5673948255617024,
      "stats": [
        {
          "count": 0,
          "type": "count",
          "name": "tryjobverifier-skip-count",
          "description": "Number of tryjob verifier runs skipped."
        },
        {
          "count": 5,
          "type": "count",
          "name": "patchset-count",
          "description": "Number of patchsets processed by the CQ."
        },
        {
          "count": 5,
          "type": "count",
          "name": "patchset-commit-count",
          "description": "Number of patchsets committed by the CQ."
        },
        {
          "count": 5,
          "type": "count",
          "name": "tryjobverifier-pass-count",
          "description": "Number of tryjob verifier runs passed."
        },
        {
          "count": 0,
          "type": "count",
          "name": "patchset-false-reject-count",
          "description": "Number of patchsets rejected by the trybots that eventually passed."
        },
        {
          "count": 5,
          "type": "count",
          "name": "trybot-pass-count",
          "description": "Number of passing runs across all trybots."
        },
        {
          "count": 0,
          "type": "count",
          "name": "trybot-infra_tester-fail-count",
          "description": "Number of failing runs by the infra_tester trybot."
        },
        {
          "count": 5,
          "type": "count",
          "name": "tryjobverifier-start-count",
          "description": "Number of tryjob verifier runs started."
        },
        {
          "count": 0,
          "type": "count",
          "name": "attempt-false-reject-trigger-count",
          "description": "Number of failed job trigger attempts on a committed patch."
        },
        {
          "count": 0,
          "type": "count",
          "name": "trybot-false-reject-count",
          "description": "Number of false rejects across all trybots. This counts any failed runs that also had passing runs on the same patch."
        },
        {
          "count": 0,
          "type": "count",
          "name": "attempt-false-reject-cq-presubmit-count",
          "description": "Number of failed CQ presubmit checks on a committed patch."
        },
        {
          "count": 0,
          "type": "count",
          "name": "tryjobverifier-retry-count",
          "description": "Number of tryjob verifier runs retried."
        },
        {
          "count": 0,
          "type": "count",
          "name": "patchset-reject-count",
          "description": "Number of patchsets rejected by the trybots at least once."
        },
        {
          "count": 5,
          "type": "count",
          "name": "trybot-infra_tester-pass-count",
          "description": "Number of passing runs by the infra_tester trybot."
        },
        {
          "count": 0,
          "type": "count",
          "name": "trybot-infra_tester-false-reject-count",
          "description": "Number of false rejects by the infra_tester trybot. This counts any failed runs that also had passing runs on the same patch."
        },
        {
          "count": 0,
          "type": "count",
          "name": "attempt-false-reject-count",
          "description": "Number of failed attempts on a committed patch that passed presubmit, had all LGTMs and were not manually cancelled."
        },
        {
          "count": 0,
          "type": "count",
          "name": "attempt-false-reject-commit-count",
          "description": "Number of failed commit attempts on a committed patch."
        },
        {
          "count": 0,
          "type": "count",
          "name": "tryjobverifier-error-count",
          "description": "Number of tryjob verifier runs errored."
        },
        {
          "count": 0,
          "type": "count",
          "name": "tryjobverifier-fail-count",
          "description": "Number of tryjob verifier runs failed."
        },
        {
          "count": 0,
          "type": "count",
          "name": "tryjobverifier-timeout-count",
          "description": "Number of tryjob verifier runs that timed out."
        },
        {
          "count": 0,
          "type": "count",
          "name": "attempt-false-reject-tryjob-count",
          "description": "Number of failed job attempts on a committed patch."
        },
        {
          "count": 0,
          "type": "count",
          "name": "trybot-fail-count",
          "description": "Number of failing runs across all trybots."
        },
        {
          "count": 5,
          "type": "count",
          "name": "issue-count",
          "description": "Number of issues processed by the CQ."
        },
        {
          "count": 5,
          "type": "count",
          "name": "attempt-count",
          "description": "Number of CQ attempts made."
        },
        {
          "description": "Time spent per committed patchset blocked on a closed tree.",
          "percentile_50": 0,
          "min": 0,
          "max": 0,
          "percentile_90": 0,
          "sample_size": 5,
          "percentile_25": 0,
          "percentile_95": 0,
          "mean": 0,
          "percentile_75": 0,
          "percentile_10": 0,
          "percentile_99": 0,
          "type": "list",
          "unit": "seconds",
          "name": "blocked-on-closed-tree-durations"
        },
        {
          "description": "Time taken by the CQ to land a patch after passing all checks.",
          "percentile_50": 3.89683,
          "min": 2.37103,
          "max": 5.97471,
          "percentile_90": 5.2368500000000004,
          "sample_size": 5,
          "percentile_25": 2.38062,
          "percentile_95": 5.605779999999999,
          "mean": 3.7506500000000003,
          "percentile_75": 4.13006,
          "percentile_10": 2.374866,
          "percentile_99": 5.900924,
          "type": "list",
          "unit": "seconds",
          "name": "patchset-commit-durations"
        },
        {
          "description": "Time spent on each tryjob verifier retry.",
          "percentile_50": 0,
          "min": 0,
          "max": 0,
          "percentile_90": 0,
          "sample_size": 0,
          "percentile_25": 0,
          "percentile_95": 0,
          "mean": 0,
          "percentile_75": 0,
          "percentile_10": 0,
          "percentile_99": 0,
          "type": "list",
          "unit": "seconds",
          "name": "tryjobverifier-retry-durations"
        },
        {
          "description": "Time spent per committed patchset blocked on a throttled tree.",
          "percentile_50": 0,
          "min": 0,
          "max": 0,
          "percentile_90": 0,
          "sample_size": 5,
          "percentile_25": 0,
          "percentile_95": 0,
          "mean": 0,
          "percentile_75": 0,
          "percentile_10": 0,
          "percentile_99": 0,
          "type": "list",
          "unit": "seconds",
          "name": "blocked-on-throttled-tree-durations"
        },
        {
          "description": "Total time spent in the CQ per patchset, counts multiple CQ attempts as one.",
          "percentile_50": 223.26259,
          "min": 191.31495,
          "max": 271.32364,
          "percentile_90": 264.574512,
          "sample_size": 5,
          "percentile_25": 222.58316,
          "percentile_95": 267.949076,
          "mean": 232.587032,
          "percentile_75": 254.45082,
          "percentile_10": 203.822234,
          "percentile_99": 270.6487272,
          "type": "list",
          "unit": "seconds",
          "name": "patchset-durations"
        },
        {
          "description": "Total time spent in the CQ per patch.",
          "percentile_50": 223.26259,
          "min": 191.31495,
          "max": 271.32364,
          "percentile_90": 264.574512,
          "sample_size": 5,
          "percentile_25": 222.58316,
          "percentile_95": 267.949076,
          "mean": 232.587032,
          "percentile_75": 254.45082,
          "percentile_10": 203.822234,
          "percentile_99": 270.6487272,
          "type": "list",
          "unit": "seconds",
          "name": "patchset-total-commit-queue-durations"
        },
        {
          "description": "Total time spent per CQ attempt on tryjob verifier runs.",
          "percentile_50": 212.13505,
          "min": 181.0709,
          "max": 260.80051,
          "percentile_90": 256.10323,
          "sample_size": 5,
          "percentile_25": 210.00244,
          "percentile_95": 258.45187,
          "mean": 222.61324199999999,
          "percentile_75": 249.05731,
          "percentile_10": 192.643516,
          "percentile_99": 260.330782,
          "type": "list",
          "unit": "seconds",
          "name": "tryjobverifier-total-durations"
        },
        {
          "description": "Total time spent per CQ attempt.",
          "percentile_50": 223.26259,
          "min": 191.31495,
          "max": 271.32364,
          "percentile_90": 264.574512,
          "sample_size": 5,
          "percentile_25": 222.58316,
          "percentile_95": 267.949076,
          "mean": 232.587032,
          "percentile_75": 254.45082,
          "percentile_10": 203.822234,
          "percentile_99": 270.6487272,
          "type": "list",
          "unit": "seconds",
          "name": "attempt-durations"
        },
        {
          "description": "Time spent on each tryjob verifier first run.",
          "percentile_50": 212.13505,
          "min": 181.0709,
          "max": 260.80051,
          "percentile_90": 256.10323,
          "sample_size": 5,
          "percentile_25": 210.00244,
          "percentile_95": 258.45187,
          "mean": 222.61324199999999,
          "percentile_75": 249.05731,
          "percentile_10": 192.643516,
          "percentile_99": 260.330782,
          "type": "list",
          "unit": "seconds",
          "name": "tryjobverifier-first-run-durations"
        },
        {
          "description": "Number of CQ attempts per patchset.",
          "percentile_50": 1,
          "min": 1,
          "max": 1,
          "percentile_90": 1,
          "sample_size": 5,
          "percentile_25": 1,
          "percentile_95": 1,
          "mean": 1,
          "percentile_75": 1,
          "percentile_10": 1,
          "percentile_99": 1,
          "type": "list",
          "unit": "attempts",
          "name": "patchset-attempts"
        },
        {
          "description": "Total time per patch since their commit box was checked.",
          "percentile_50": 223.26259,
          "min": 191.31495,
          "max": 271.32364,
          "percentile_90": 264.574512,
          "sample_size": 5,
          "percentile_25": 222.58316,
          "percentile_95": 267.949076,
          "mean": 232.587032,
          "percentile_75": 254.45082,
          "percentile_10": 203.822234,
          "percentile_99": 270.6487272,
          "type": "list",
          "unit": "seconds",
          "name": "patchset-total-wall-time-durations"
        }
      ]
    },
  ],
  "more": true
};
