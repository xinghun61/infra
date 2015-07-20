# Gsubtreed

#### (git subtree daemon)

Gsubtreed is a daemon which mirrors subtrees from a large git repo to their
own smaller repos. It is typically run for medium-term intervals (e.g. 10 min),
restarting after every interval. While it's running it has a short (e.g. 5s)
poll+process cycle for the repo that it's mirroring.

## Setup:

1.  Push a file named `config.json` to the `refs/gsubtreed-config/main` ref of
    the repo you intend to mirror. Its contents is determined by
    [`GsubtreedConfigRef`][1]. You must at least set the `enabled_paths`
    portion.
    *   You should create a new line of history (e.g. `git checkout --orphan`)
        to avoid having unecessary extra files in this ref (as opposed to
        branching it off of another ref like `master`). Note that you'll
        probably also want to do a `git rm -rf` after you check out the orphan
        ref to clear the index+working copy.
1.  (optional) If you have existing git mirrors (probably mirrored via git-svn),
    disable the mirroring service for them. If not, create the mirrors. By
    default if gsubtreed mirrors the path `bob` in `https://.../repo`, it will
    expect to find the mirror repo at `https://.../repo/bob`. You can change
    this with the `base_url` parameter in the config.
    *   If you do have existing mirrors, you will also need to bootstrap them.
        gsubtreed uses the mirror repos to store state about what it has already
        processed. It stores state as commit footers (e.g. `Cr-Mirrored-From`)
        The existing mirrors don't have this state so we have to cheat.

    *   gsubtreed has a feature which allows it to pretend as if a given commit
        has extra commit footers that it doesn't really have. These are stored
        in a git-notes ref `refs/notes/extra_footers` using the `git notes`
        tool.  Setting them requires finding the commit in the original git repo
        which corresponds with the commit in the mirror repo.

    *   The tool `run.py infra.services.gsubtreed.bootstrap_from_existing` does
        most of this work for you, but it's not bullet-proof and tends to assume
        a lot of things about how the repos are related to each other (it was
        written as a one-off to assist the chromium git migration). However
        studying its source code should be enlightening.

    *   Note that `git notes` may not respect the `--ref` option with a fully
        qualified ref (e.g. `refs/notes/extra_footers`). For example, `git notes
        --ref refs/b/l/a add ...` may actually store notes in
        `refs/notes/refs/b/l/a`. You can check which ref is really being used by
        running `git notes --ref refs/b/l/a get-ref`.  If you have this problem
        AND your mirrors already have notes in `refs/notes/extra_footers`, you
        may have to locally inititalize the weird ref (the `get-ref` one) with
        the commit hash of `refs/notes/extra_footers` of your mirror. You can do
        this directly with the `git update-ref` command after fetching the
        existing notes from the mirror.

1.  Once your mirrors are in a good state (either empty or primed with
    `extra_footers`), you should be able to run: `run.py
    infra.services.gsubtreed <repo url>` and it should Just Work.

1.  At this point you should set up a new bot on the [infra cron waterfall][2]
    to run this on a regular interval.

## Usage:

    run.py infra.services.gsubtreed <repo_url>

## GsubtreedConfigRef fields

*   `interval` *number*: The time in seconds between iterations of gsubtreed.
    Each iteration will fetch from the main repo, and try to push to all of the
    subtree repos.

*   `base_url` *string*: The base URL is the url relative to which all mirror
    repos are assumed to exist. For example, if you mirror the path `bob`, and
    base_url is `https://.../main_repo`, then it would assume that the mirror
    for the `bob` subtree is `https://.../main_repo/bob`.  By default, base_url
    is set to the repo that gsubtreed is processing.

*   `enabled_paths` *[string]*: A list of paths in the repo to mirror. These are
    absolute paths from the ref root. Any commits which affect these paths will
    be mirrored to the target repo `'/'.join((base_url, path))`.

*   `enabled_refglobs` *[string]*: A list of git-style absolute refglobs that
    gsubtreed should attempt to mirror. If a subtree appears in multiple refs
    covered by the refglob, then all of those refs will be pushed to the mirror
    for that subtree. Say you are mirroring the subtree `bob` and the refglob
    `refs/*`. If `bob` appeared on `refs/foo` and `refs/bar`, the `bob` subtree
    repo would then contain both a `refs/foo` and a `refs/bar` ref.

*   `path_map_exceptions` *{string: string}*: A dictionary mapping
    `enabled_path` to 'mirror_repo_path'. This will be used instead of the
    generic join rule for calculating the mirror URL (so it would be
    `'/'.join((base_url, path_map_exceptions[path]))` instead of using path
    directly). For example if this had the value `{'path/to/foo': 'bar'}`, and
    base_url was `https://example.com`, then it would mirror `path/to/foo` to
    `https://example.com/bar`, instead of `https://example.com/path/to/foo`.

*   `path_extra_push` *{string: [string]}*: A dictionary mapping `enabled_path`
    to a list of full_git_repo_urls. Any time we find changes in the
    enabled_path, we'll also push those subtree commits to all the git repos in
    full_git_repo_urls.

[1]: ./gsubtreed.py#32
[2]: http://build.chromium.org/p/chromium.infra.cron
