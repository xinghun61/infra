## Python Patching

Unfortunately, Infra has to make some changes to Python to get it to statically
compile.

If the patches don't land, you can manually apply them by running the `git am`
command:

```sh
export TAG=refs/tags/v2.14.1
export TPP_PATCHES=/path/to/this/dir
git clone https://chromium.googlesource.com/external/github.com/python/cpython
git fetch origin $TAG
git checkout -b patch FETCH_HEAD
git am --reject $TPP_PATCHES/*.patch

# If the patches fail to apply, you can resolve the problems, add the results to
# the current commit, and continue. Repeat until all patches land.
git add ...
git am --continue

# Finally, regenerate the patch set. Use a limited diff context so we don't
# pull in version-specific information.
git format-patch -U2 FETCH_HEAD -o $TPP_PATCHES/
```

## Dry Runs

Each `third_party_packages` module can be dry-run via example:

```sh
./recipes/recipes.py run \
  --workdir $HOME/temp/recipes/workdir \
  --properties '{"dry_run": true}' \
  third_party_packages:examples/python
```
