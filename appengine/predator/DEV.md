# Contribution

[TOC]

# How to checkout code and make change?

Follow the general infra development flow [here](../../doc/source.md)

# How to deploy to appengine?

For testing on the staging app, deploy to predator-for-me-staging.appspot.com:
  infra/appengine/predator/scripts/run.sh deploy-test-staging

For staging test on the product app, deploy to predator-for-me.appspot.com:
  infra/appengine/predator/scripts/run.sh deploy-test-prod

For release, deploy to predator-for-me.appspot.com:
  infra/appengine/predator/scripts/run.sh deploy-prod
Please carefully follow the messages by the script for the deployment.

# Monitoring

(1) Internal dashboards to monitor all the results:
Clusterfuzz (aarya@, mbarbella@): https://predator-for-me.appspot.com/clusterfuzz/dashboard
Fracas (jchinlee@): https://predator-for-me.appspot.com/fracas/dashboard
Cracas (ivanpe@): https://predator-for-me.appspot.com/cracas/dashboard
UMA Sampling Profiler (wittman@): https://predator-for-me.appspot.com/uma-sampling-profiler/dashboard

(2) Monitor metrics using vicerory dashboards:
go/predator-metrics

# Testing and Debug

(1) How to run unittests?

From command line, run:
  infra/appengine/predator/scripts/run.sh test

If a code path branch is not tested and no line number is shown in the command
line output, you could check the code coverage report shown in the output.

(2) How to run Predator service locally?

From command line, run:
  infra/appengine/predator/scripts/run.sh run

Then open http://localhost:8080 for the home page.

(3) How to run Predator on a real crash testcase?

Given the urlsafe encoding of the key of a CrashAnalysis(The urlsafe encoding
can be found in dashboards for client, you can search by signature of this crash
in dashboards), we can run local code of Predator on this crash.

For example:
For a clusterfuzz crash:
https://predator-for-me.appspot.com/clusterfuzz/result-feedback?key=ahFzfnByZWRhdG9yLWZvci1tZXJBCxITQ2x1c3RlcmZ1enpBbmFseXNpcyIoZDNhN2RhNDcyYzE2YmQ5ODkwMWM2ZjhjNmUwNWQ1YjIxMzU1ZDA2Mww
The key is ahFzfnByZWRhdG9yLWZvci1tZXJBCxITQ2x1c3RlcmZ1enpBbmFseXNpcyIoZDNhN2RhNDcyYzE2YmQ5ODkwMWM2ZjhjNmUwNWQ1YjIxMzU1ZDA2Mww
Given the key, we can run local command:
  infra/appengine/predator/scripts/run-predator -k ahFzfnByZWRhdG9yLWZvci1tZXJBCxITQ2x1c3RlcmZ1enpBbmFseXNpcyIoZDNhN2RhNDcyYzE2YmQ5ODkwMWM2ZjhjNmUwNWQ1YjIxMzU1ZDA2Mww -v

In this way, we can experiment local changes using real testcases.

Debug:
  you can set breakpoint anywhere when running Predator using this script by:
  import pdb; pdb.set_trace()
