## Git Patching

Unfortunately, Infra has to make some changes to Git to get it to work in an
Infra environment.

If the patches don't land, you can manually apply them by running the `git am`
command:

```sh
export TAG=refs/tags/v2.14.1
export TPP_GIT_PATCHES=/path/to/this/dir
git clone https://chromium.googlesource.com/external/github.com/git/git
git fetch origin $TAG
git checkout -b patch FETCH_HEAD
git am --reject $TPP_GIT_PATCHES/*.patch

# If the patches fail to apply, you can resolve the problems, add the results to
# the current commit, and continue. Repeat until all patches land.
git add ...
git am --continue

# Finally, regenerate the patch set:
git format-patch refs/tags/v2.14.1 -o $TPP_GIT_PATCHES/
```

## Dry Runs

Each `third_party_packages` module can be dry-run via example:

```sh
./recipes/recipes.py run \
  --workdir $HOME/temp/recipes/workdir \
  --properties '{"dry_run": true}' \
  third_party_packages:examples/git
```
