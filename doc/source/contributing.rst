Contributing to infra.git
=========================

Standard workflow
-----------------
Starting with an configured checkout, here's the standard workflow to make a
modification to the source code:

* Make sure your code is up-to-date: run ``gclient sync`` anywhere in infra.git.
* Create a new branch: ``git new-branch``.
* Make modifications, commit them using ``git commit``.
* Upload your modification for review by running ``git cl upload``. This step
  runs the tests, which must pass. If they don't, go back to the previous step
  to fix any issue. You can use ``test.py`` to run tests anytime. Make sure
  you've added reviewers for your modifications.
* Once your code has been approved, you can commit it by clicking the 'commit'
  checkbox on the code review tool, or by running ``git cl land`` if you're
  a Chromium committer.


Deployment process
------------------
As of September 2014 there is no formal deployment process. To make your changes
live, you have to ask on chrome-troopers@google.com.


How to add a dependency
-----------------------
Sometimes it is necessary to add a new Python package to the virtual
environment. See instructions in :doc:`bootstrap`.

