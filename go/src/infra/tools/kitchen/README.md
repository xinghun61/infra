# kitchen

kitchen is a binary that bootstraps a swarmbucket build on a bot and runs a
recipe. Its command line is specified in
[swarmbucket's swarming_task_template](https://chrome-internal.googlesource.com/infradata/config/+/master/configs/cr-buildbucket/swarming_task_template.json)


## CIPD package

Kitchen CIPD packages have prefix "infra/tools/luci/kitchen/".
They are being continuously created by master.chromium.infra master for each
platform, e.g.
[for OS X](https://build.chromium.org/p/chromium.infra/builders/infra-continuous-mac-10.11-64).
