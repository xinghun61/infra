"""Gsubtreed is a daemon which mirrors subtrees from a large git repo to their
own smaller repos. It is typically run for medium-term intervals (e.g. 10 min),
restarting after every interval. While it's running it has a short (e.g. 5s)
poll+process cycle for the repo that it's mirroring.

Setup:
  1. Push a file named 'config.json' to the 'refs/gsubtreed-config/main' ref of
     the repo you intend to mirror. Its contents is determined by
     :class:`~gsubtreed.GsubtreedConfigRef`. You must at least set the
     `enabled_paths` portion.
  2. If you have existing git mirrors (probably mirrored via git-svn), disable
     the mirroring service for them. If not, create the mirrors. By default
     if gsubtreed mirrors the path ``bob`` in ``https://.../repo``, it will
     expect to find the mirror repo at ``https://.../repo/bob``. You can change
     this with the `base_url` parameter in the config.
    a. If you do have existing mirrors, you will also need to bootstrap them.
       gsubtreed uses the mirror repos to store state about what it has already
       processed. It stores state as commit footers (e.g. ``Cr-Mirrored-From``)
       The existing mirrors don't have this state so we have to cheat.

       gsubtreed has a feature which allows it to pretend as if a given commit
       has extra commit footers that it doesn't really have. These are stored
       in a git-notes ref ``refs/notes/extra_footers`` using the ``git notes``
       tool. Setting them requires finding commit in the original git repo which
       corresponds with the commit in the repo.

       The tool ``run.py infra.services.gsubtreed.bootstrap_from_existing`` does
       most of this work for you, but it's not bullet proof and tends to assume
       a lot of things about how the repos are related to each other (it was
       written as a one-off to assist the chromium git migration). However
       studying its source code should be enlightening.
  3. Once your mirrors are in a good state (either empty or primed with
     ``extra_footers``), you should be able to run ``run.py
     infra.services.gsubtreed <repo Url>`` and it should Just Work.
  4. At this point you should set up a new bot on the infra waterfall to run
     this on a regular interval.

Usage:
  run.py infra.services.gsubtreed <repo_url>

"""
