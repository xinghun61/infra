# Contributing to infra.git

[TOC]

## Standard workflow

Starting with an [configured checkout](source.md), here's the standard workflow
to make a modification to the source code:

1. Make sure your code is up-to-date: run `gclient sync` anywhere in
   infra.git.
2. Create a new branch: `git new-branch <branch-name>`.
3. Make modifications, commit them using `git commit`.
4. Upload your modification for review by running `git cl upload`. This
   step runs the tests, which must pass. If they don't, go back to the
   previous step to fix any issue. You can use [test.py](../test.py) to run
   tests anytime. Make sure you've added reviewers for your modifications and
   sent an email.
5. Once your code has been approved, you can commit it by clicking the
   "Commit" checkbox on the code review tool, or by running
   `git cl land` if you're a Chromium committer.
   For old SVN-based repos, use `git cl dcommit` instead of `git cl land`.

# Gerrit CLs

Workflow:

1. Upload CL to Gerrit: `git push origin HEAD:refs/for/master`.
   The output should contain a link to the new CL.
2. Manually add reviewers to the CL.
3. Send "PTAL" and set `Verified +1` if you verified your code works.
   Use "Reply" button in the top.
4. Make changes online, or send a second patchset:
   copy "Change-Id: 1234567890" from the CL to the
   end of the local commit message.
   Then do `git push origin HEAD:refs/for/master` again.
5. When you receive `Code-Review +2` and `Verified +1`, you can press "Submit"
   button in webui.

If Gerrit is the only codereview you use for a given repo, install
[commit-msg hook](https://gerrit.googlecode.com/svn/documentation/2.0/cmd-hook-commit-msg.html)
to avoid copying Change-Id.

## Deployment process

As of July 2015 there is no formal deployment process. To make your
changes live, you have to ask on chrome-troopers@google.com.

## How to add a dependency

Sometimes it is necessary to add a new Python package to the virtual
environment. See instructions in [/bootstrap/](../bootstrap/README.md).

## Troubleshooting

### git-cl-dcommit fails

Try running `git auto-svn` to fix it.
If that fails, ignore most of the error message, except the `svn://` URL
at the end. Take that URL and run
`svn --username ${USER?}@google.com ls ${SVN_URL?}` ... and if it asks
for a password, visit
[chromium-access.appspot.com](https://chromium-access.appspot.com)

If you get an error message like this:

    Attempting to commit more than one change while --no-rebase is enabled. If
    these changes depend on each other, re-running without --no-rebase may be
    required. at /usr/lib/git-core/git-svn line 876.

    ERROR from SVN:
    Item already exists in filesystem: File already exists: filesystem
    '/opt/repos/chromium/db', transaction '63626-1edr', path
    '/trunk/remoting/tools/foobar.json'

Then do this:

    git svn fetch

If that is insufficient, then do this:

    rm -rf .git/svn
    git checkout master
    git svn fetch
