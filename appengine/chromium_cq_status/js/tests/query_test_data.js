var query_test_data = {
  "cursor": "SoMeCuRsOr",
  "results": [
    {
      "timestamp": 1434070754.91433,
      "fields": {
        "status": "ready_to_commit",
        "dry_run": false,
        "timestamp": 1434070754.883375,
        "state": "",
        "project": "infra",
        "owner": "nobody@chromium.org",
        "reason": null,
        "done": true,
        "action": "patch_ready_to_commit",
        "patchset": 40001,
        "issue": 0152223302,
        "message": ""
      },
      "key": null,
      "tags": [
        "action=patch_ready_to_commit",
        "patchset=40001",
        "owner=nobody@chromium.org",
        "issue=0152223302",
        "project=infra"
      ]
    },
    {
      "timestamp": 1434070752.2825,
      "fields": {
        "status": "stop",
        "dry_run": false,
        "timestamp": 1434070752.184226,
        "state": "",
        "project": "infra",
        "owner": "nobody@chromium.org",
        "reason": null,
        "done": true,
        "action": "patch_stop",
        "patchset": 40001,
        "issue": 0152223302,
        "message": "Patch successfully committed."
      },
      "key": null,
      "tags": [
        "patchset=40001",
        "owner=nobody@chromium.org",
        "issue=0152223302",
        "action=patch_stop",
        "project=infra"
      ]
    },
    {
      "timestamp": 1434070752.21769,
      "fields": {
        "status": "committed",
        "dry_run": false,
        "timestamp": 1434070752.184123,
        "state": "",
        "project": "infra",
        "owner": "nobody@chromium.org",
        "reason": null,
        "done": true,
        "action": "patch_committed",
        "patchset": 40001,
        "issue": 0152223302,
        "message": ""
      },
      "key": null,
      "tags": [
        "patchset=40001",
        "owner=nobody@chromium.org",
        "issue=0152223302",
        "action=patch_committed",
        "project=infra"
      ]
    },
    {
      "timestamp": 1434070749.83707,
      "fields": {
        "status": "committing",
        "dry_run": false,
        "timestamp": 1434070749.706798,
        "state": "",
        "project": "infra",
        "owner": "nobody@chromium.org",
        "reason": null,
        "done": true,
        "action": "patch_committing",
        "patchset": 40001,
        "issue": 0152223302,
        "message": ""
      },
      "key": null,
      "tags": [
        "action=patch_committing",
        "patchset=40001",
        "owner=nobody@chromium.org",
        "issue=0152223302",
        "project=infra"
      ]
    },
    {
      "timestamp": 1434070744.77681,
      "fields": {
        "status": "ready_to_commit",
        "dry_run": false,
        "timestamp": 1434070744.658891,
        "state": "",
        "project": "infra",
        "owner": "nobody@chromium.org",
        "reason": null,
        "done": true,
        "action": "patch_ready_to_commit",
        "patchset": 40001,
        "issue": 0152223302,
        "message": ""
      },
      "key": null,
      "tags": [
        "action=patch_ready_to_commit",
        "patchset=40001",
        "owner=nobody@chromium.org",
        "issue=0152223302",
        "project=infra"
      ]
    },
    {
      "timestamp": 1434070744.67136,
      "fields": {
        "status": "start",
        "dry_run": false,
        "state": "",
        "timestamp": 1434070744.58242,
        "verifier": "try job",
        "project": "infra",
        "owner": "nobody@chromium.org",
        "attempt_start_ts": 1434070481416440,
        "done": true,
        "action": "verifier_pass",
        "patchset": 40001,
        "issue": 0152223302
      },
      "key": null,
      "tags": [
        "owner=nobody@chromium.org",
        "patchset=40001",
        "issue=0152223302",
        "verifier=try job",
        "action=verifier_pass",
        "project=infra"
      ]
    },
    {
      "timestamp": 1434070744.6167,
      "fields": {
        "status": "start",
        "project": "infra",
        "jobs": {
          "JOB_SUCCEEDED": [
            {
              "build_id": "9043261822262727792",
              "parent_name": null,
              "tests": [
                "defaulttests"
              ],
              "slave": "vm000-c4",
              "url": "http://build.chromium.org/p/tryserver.chromium.linux/builders/infra_tester/builds/9999",
              "timestamp": "2015-06-12 00:58:58.194440",
              "builder": "infra_tester",
              "clobber": null,
              "project": "",
              "reason": "CQ",
              "master": "tryserver.chromium.linux",
              "result": 0,
              "key": "ahdzfmNocm9taXVtY29kZXJldmlldy1ocnIwCxIXQnVpbGRidWNrZXRUcnlKb2JSZXN1bHQiEzkwNDMyNjE4MjIyNjI3Mjc3OTIM",
              "requester": "commit-bot@chromium.org",
              "buildnumber": 9999,
              "category": "cq",
              "build_properties": {
                "got_revision": "a905d1305e010fd9cbc2717988bf89a66a5c6d8a",
                "recipe": "infra/infra_repo_trybot",
                "patch_project": "infra",
                "category": "cq",
                "project": "",
                "slavename": "vm000-c4",
                "attempt_start_ts": 1434070481416440,
                "blamelist": [
                  "nobody@chromium.org"
                ],
                "branch": null,
                "master": "tryserver.chromium.linux",
                "patchset": 40001,
                "issue": 0152223302,
                "revision": "",
                "workdir": "/b/build/slave/infra_tester",
                "repository": "",
                "buildername": "infra_tester",
                "testfilter": [
                  "defaulttests"
                ],
                "mastername": "tryserver.chromium.linux",
                "patch_storage": "rietveld",
                "reason": "CQ",
                "requester": "commit-bot@chromium.org",
                "buildbotURL": "http://build.chromium.org/p/tryserver.chromium.linux/",
                "rietveld": "https://codereview.chromium.org",
                "buildnumber": 9999,
                "requestedAt": 1434070504
              },
              "job_state": "JOB_SUCCEEDED",
              "revision": ""
            }
          ]
        },
        "dry_run": false,
        "state": "",
        "timestamp": 1434070744.582245,
        "verifier": "try job",
        "job_states": {
          "tryserver.chromium.linux:infra_tester": "JobState(state=JOB_SUCCEEDED)"
        },
        "owner": "nobody@chromium.org",
        "attempt_start_ts": 1434070481416440,
        "done": false,
        "action": "verifier_jobs_update",
        "diff": {
          "JOB_RUNNING": "KEY_MISSING",
          "JOB_SUCCEEDED": [
            {
              "build_id": "9043261822262727792",
              "parent_name": null,
              "tests": [
                "defaulttests"
              ],
              "slave": "vm000-c4",
              "url": "http://build.chromium.org/p/tryserver.chromium.linux/builders/infra_tester/builds/9999",
              "timestamp": "2015-06-12 00:58:58.194440",
              "builder": "infra_tester",
              "clobber": null,
              "project": "",
              "reason": "CQ",
              "master": "tryserver.chromium.linux",
              "result": 0,
              "key": "ahdzfmNocm9taXVtY29kZXJldmlldy1ocnIwCxIXQnVpbGRidWNrZXRUcnlKb2JSZXN1bHQiEzkwNDMyNjE4MjIyNjI3Mjc3OTIM",
              "requester": "commit-bot@chromium.org",
              "buildnumber": 9999,
              "category": "cq",
              "build_properties": {
                "got_revision": "a905d1305e010fd9cbc2717988bf89a66a5c6d8a",
                "recipe": "infra/infra_repo_trybot",
                "patch_project": "infra",
                "category": "cq",
                "project": "",
                "slavename": "vm000-c4",
                "attempt_start_ts": 1434070481416440,
                "blamelist": [
                  "nobody@chromium.org"
                ],
                "branch": null,
                "master": "tryserver.chromium.linux",
                "patchset": 40001,
                "issue": 0152223302,
                "revision": "",
                "workdir": "/b/build/slave/infra_tester",
                "repository": "",
                "buildername": "infra_tester",
                "testfilter": [
                  "defaulttests"
                ],
                "mastername": "tryserver.chromium.linux",
                "patch_storage": "rietveld",
                "reason": "CQ",
                "requester": "commit-bot@chromium.org",
                "buildbotURL": "http://build.chromium.org/p/tryserver.chromium.linux/",
                "rietveld": "https://codereview.chromium.org",
                "buildnumber": 9999,
                "requestedAt": 1434070504
              },
              "job_state": "JOB_SUCCEEDED",
              "revision": ""
            }
          ]
        },
        "patchset": 40001,
        "issue": 0152223302
      },
      "key": null,
      "tags": [
        "owner=nobody@chromium.org",
        "verifier=try job",
        "patchset=40001",
        "issue=0152223302",
        "action=verifier_jobs_update",
        "project=infra"
      ]
    },
    {
      "timestamp": 1434070506.28077,
      "fields": {
        "status": "start",
        "project": "infra",
        "jobs": {
          "JOB_RUNNING": [
            {
              "build_id": "9043261822262727792",
              "parent_name": null,
              "tests": [
                "defaulttests"
              ],
              "slave": null,
              "url": "http://build.chromium.org/p/tryserver.chromium.linux/builders/infra_tester/builds/9999",
              "timestamp": "2015-06-12 00:55:04.806000",
              "builder": "infra_tester",
              "clobber": null,
              "project": null,
              "reason": "CQ",
              "master": "tryserver.chromium.linux",
              "result": -1,
              "key": "ahdzfmNocm9taXVtY29kZXJldmlldy1ocnIwCxIXQnVpbGRidWNrZXRUcnlKb2JSZXN1bHQiEzkwNDMyNjE4MjIyNjI3Mjc3OTIM",
              "requester": null,
              "buildnumber": null,
              "category": "cq",
              "build_properties": {
                "category": "cq",
                "rietveld": "https://codereview.chromium.org",
                "testfilter": [
                  "defaulttests"
                ],
                "patch_storage": "rietveld",
                "attempt_start_ts": 1434070481416440,
                "master": "tryserver.chromium.linux",
                "reason": "CQ",
                "patchset": 40001,
                "issue": 0152223302,
                "patch_project": "infra",
                "revision": "HEAD"
              },
              "job_state": "JOB_RUNNING",
              "revision": "HEAD"
            }
          ]
        },
        "dry_run": false,
        "state": "",
        "timestamp": 1434070506.241574,
        "verifier": "try job",
        "job_states": {
          "tryserver.chromium.linux:infra_tester": "JobState(state=JOB_RUNNING)"
        },
        "owner": "nobody@chromium.org",
        "attempt_start_ts": 1434070481416440,
        "done": false,
        "action": "verifier_jobs_update",
        "diff": {
          "JOB_RUNNING": [
            {
              "build_id": "9043261822262727792",
              "parent_name": null,
              "tests": [
                "defaulttests"
              ],
              "slave": null,
              "url": "http://build.chromium.org/p/tryserver.chromium.linux/builders/infra_tester/builds/9999",
              "timestamp": "2015-06-12 00:55:04.806000",
              "builder": "infra_tester",
              "clobber": null,
              "project": null,
              "reason": "CQ",
              "master": "tryserver.chromium.linux",
              "result": -1,
              "key": "ahdzfmNocm9taXVtY29kZXJldmlldy1ocnIwCxIXQnVpbGRidWNrZXRUcnlKb2JSZXN1bHQiEzkwNDMyNjE4MjIyNjI3Mjc3OTIM",
              "requester": null,
              "buildnumber": null,
              "category": "cq",
              "build_properties": {
                "category": "cq",
                "rietveld": "https://codereview.chromium.org",
                "testfilter": [
                  "defaulttests"
                ],
                "patch_storage": "rietveld",
                "attempt_start_ts": 1434070481416440,
                "master": "tryserver.chromium.linux",
                "reason": "CQ",
                "patchset": 40001,
                "issue": 0152223302,
                "patch_project": "infra",
                "revision": "HEAD"
              },
              "job_state": "JOB_RUNNING",
              "revision": "HEAD"
            }
          ],
          "JOB_PENDING": "KEY_MISSING"
        },
        "patchset": 40001,
        "issue": 0152223302
      },
      "key": null,
      "tags": [
        "owner=nobody@chromium.org",
        "verifier=try job",
        "patchset=40001",
        "issue=0152223302",
        "action=verifier_jobs_update",
        "project=infra"
      ]
    },
    {
      "timestamp": 1434070497.24857,
      "fields": {
        "status": "start",
        "project": "infra",
        "jobs": {
          "JOB_PENDING": [
            {
              "build_id": "9043261822262727792",
              "parent_name": null,
              "tests": [
                "defaulttests"
              ],
              "slave": null,
              "url": null,
              "timestamp": "2015-06-12 00:54:45.778320",
              "builder": "infra_tester",
              "clobber": null,
              "project": null,
              "reason": "CQ",
              "master": "tryserver.chromium.linux",
              "result": 6,
              "key": "ahdzfmNocm9taXVtY29kZXJldmlldy1ocnIwCxIXQnVpbGRidWNrZXRUcnlKb2JSZXN1bHQiEzkwNDMyNjE4MjIyNjI3Mjc3OTIM",
              "requester": null,
              "buildnumber": null,
              "category": "cq",
              "build_properties": {
                "category": "cq",
                "rietveld": "https://codereview.chromium.org",
                "testfilter": [
                  "defaulttests"
                ],
                "patch_storage": "rietveld",
                "attempt_start_ts": 1434070481416440,
                "master": "tryserver.chromium.linux",
                "reason": "CQ",
                "patchset": 40001,
                "issue": 0152223302,
                "patch_project": "infra",
                "revision": "HEAD"
              },
              "job_state": "JOB_PENDING",
              "revision": "HEAD"
            }
          ]
        },
        "dry_run": false,
        "state": "",
        "timestamp": 1434070497.214346,
        "verifier": "try job",
        "job_states": {
          "tryserver.chromium.linux:infra_tester": "JobState(state=JOB_PENDING)"
        },
        "owner": "nobody@chromium.org",
        "attempt_start_ts": 1434070481416440,
        "done": false,
        "action": "verifier_jobs_update",
        "diff": {
          "JOB_PENDING": [
            {
              "build_id": "9043261822262727792",
              "parent_name": null,
              "tests": [
                "defaulttests"
              ],
              "slave": null,
              "url": null,
              "timestamp": "2015-06-12 00:54:45.778320",
              "builder": "infra_tester",
              "clobber": null,
              "project": null,
              "reason": "CQ",
              "master": "tryserver.chromium.linux",
              "result": 6,
              "key": "ahdzfmNocm9taXVtY29kZXJldmlldy1ocnIwCxIXQnVpbGRidWNrZXRUcnlKb2JSZXN1bHQiEzkwNDMyNjE4MjIyNjI3Mjc3OTIM",
              "requester": null,
              "buildnumber": null,
              "category": "cq",
              "build_properties": {
                "category": "cq",
                "rietveld": "https://codereview.chromium.org",
                "testfilter": [
                  "defaulttests"
                ],
                "patch_storage": "rietveld",
                "attempt_start_ts": 1434070481416440,
                "master": "tryserver.chromium.linux",
                "reason": "CQ",
                "patchset": 40001,
                "issue": 0152223302,
                "patch_project": "infra",
                "revision": "HEAD"
              },
              "job_state": "JOB_PENDING",
              "revision": "HEAD"
            }
          ]
        },
        "patchset": 40001,
        "issue": 0152223302
      },
      "key": null,
      "tags": [
        "owner=nobody@chromium.org",
        "verifier=try job",
        "patchset=40001",
        "issue=0152223302",
        "action=verifier_jobs_update",
        "project=infra"
      ]
    },
    {
      "timestamp": 1434070486.41853,
      "fields": {
        "status": "start",
        "dry_run": false,
        "state": "",
        "timestamp": 1434070486.381273,
        "verifier": "try job",
        "project": "infra",
        "owner": "nobody@chromium.org",
        "attempt_start_ts": 1434070481416440,
        "done": false,
        "action": "verifier_trigger",
        "patchset": 40001,
        "issue": 0152223302,
        "trybots": {
          "tryserver.chromium.linux": {
            "infra_tester": [
              "defaulttests"
            ]
          }
        }
      },
      "key": null,
      "tags": [
        "verifier=try job",
        "patchset=40001",
        "issue=0152223302",
        "owner=nobody@chromium.org",
        "project=infra",
        "action=verifier_trigger"
      ]
    },
    {
      "timestamp": 1434070483.87085,
      "fields": {
        "status": "start",
        "dry_run": false,
        "state": "",
        "timestamp": 1434070483.51435,
        "verifier": "try job",
        "project": "infra",
        "owner": "nobody@chromium.org",
        "attempt_start_ts": 1434070481416440,
        "done": true,
        "action": "verifier_start",
        "patchset": 40001,
        "issue": 0152223302
      },
      "key": null,
      "tags": [
        "verifier=try job",
        "patchset=40001",
        "issue=0152223302",
        "owner=nobody@chromium.org",
        "action=verifier_start",
        "project=infra"
      ]
    },
    {
      "timestamp": 1434070480.95886,
      "fields": {
        "status": "start",
        "dry_run": false,
        "timestamp": 1434070480.92661,
        "state": "",
        "project": "infra",
        "owner": "nobody@chromium.org",
        "reason": null,
        "done": false,
        "action": "patch_start",
        "patchset": 40001,
        "issue": 0152223302,
        "message": ""
      },
      "key": null,
      "tags": [
        "patchset=40001",
        "owner=nobody@chromium.org",
        "action=patch_start",
        "issue=0152223302",
        "project=infra"
      ]
    }
  ],
  "more": false
};
