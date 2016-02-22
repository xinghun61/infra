# Try your recipe before committing

*aka [go/test](http://go/try-recipe)*

## tl;dr


    # hack, hack, commit, upload my_recipe.py
    export MY_RECIPE=my_recipe
    git cl try -m tryserver.infra \
          -b "Try Recipe Win 64" -b "Try Recipe Mac" -b "Try Recipe Trusty 64" \
          -p try_recipe="$MY_RECIPE" \
          -p try_props=$(echo '{"add_yours":"here"}' | \
                python -c "import zlib, sys, base64; \
                      print base64.b64encode(zlib.compress(sys.stdin.read()))")
    git cl web  
    # Click on started tryjobs and examine the runs.

## Example

See https://codereview.chromium.org/1719743003/ while tryjobs remain on the master.


## How does it work?

The try_recipe is actually very simple:

    1. Check out build repo.
    2. Applies your patch on top.
    3. Execute your recipe with your properties.


## Future

With [LUCI](https://github.com/luci), the recipes would finally be client-side,
and you'd be able to try your changes to them as normal tryjobs of your project.
