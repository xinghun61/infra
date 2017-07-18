# Quick build system overview

There is a good overview
[here](https://chromium.googlesource.com/infra/infra/+/master/doc/users/services/buildbot/builders.pyl.md#Overview).

# Adding a new builder

There is a good overview
[here](https://chromium.googlesource.com/chromium/tools/build.git/+/master/scripts/slave/recipe_modules/chromium_tests/chromium_recipe.md#Create-a-New-Builder).

# Other questions

## Can builders share the same host?

Yes. However, build directories can be large and cause the bot to run out of
space. Keep this in mind when assigning the same host to multiple builders. If
the builders can share the same build directory, specify that using
[botbuilddir](https://chromium.googlesource.com/infra/infra/+/master/doc/users/services/buildbot/builders.pyl.md#botbuilddir)
in builders.pyl (if your master has one) or in slave.cfg.
