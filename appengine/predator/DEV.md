# Contribution

[TOC]

# How to checkout code and make change?

Follow the general infra development flow [here](../../doc/source.md)

# How to run Predator locally?

From command line, run:
  infra/appengine/predator/scripts/run.sh run

Then open http://localhost:8080 for the home page.

# How to run unittests?

From command line, run:
  infra/appengine/predator/scripts/run.sh test

If a code path branch is not tested and no line number is shown in the command
line output, you could check the code coverage report shown in the output.

# How to run Predator on a certain crash?

Given the urlsafe encoding of the key of a CrashAnalysis, we can run local
version of Predator on this crash.

For example:
Given a crash id ahpzfmdvb2dsZS5jb2 (This is a fake id for demonstration)

From command line, run:
  infra/appengine/predator/scripts/run-predator -k ahpzfmdvb2dsZS5jb2 -v

Debug:
  you can set breakpoint anywhere when running Predator using this script by:
  import pdb; pdb.set_trace()

# How to deploy to appengine?

For testing on the staging app, deploy to predator-for-me-staging.appspot.com:
  infra/appengine/predator/scripts/run.sh deploy-test-staging

For staging test on the product app, deploy to predator-for-me.appspot.com:
  infra/appengine/predator/scripts/run.sh deploy-test-prod

For release, deploy to predator-for-me.appspot.com:
  infra/appengine/predator/scripts/run.sh deploy-prod
Please carefully follow the messages by the script for the deployment.
