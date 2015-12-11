# Buildbucket-Swarming integration.

Buildbucket has native integration with swarming and recipes.
A bucket can be configured so a build for a builder is scheduled on swarming
to run a specific recipe.

[TOC]

## Configuration

### Per bucket

A bucket entry in buildbucket config may have `swarming` key, for example:

    buckets {
      name: "foobar"

      swarming {
        hostname: "chromium-swarm.appspot.com"
        builders {
          name: "Linux-Release"
          dimensions {
            key: "os"
            value: "Linux"
          }
          recipe {
            repository: "https://chromium.googlesource.com/chromium/tools/build"
            name: "chromium"
          }
        }
        builders {
          name: "Windows-Release"
          dimensions {
            key: "os"
            value: "Windows"
          }
          recipe {
            repository: "https://chromium.googlesource.com/chromium/tools/build"
            name: "chromium"
          }
        }
      }
    }

For format and documentation see `Swarming` message in the
[project_config.proto](../proto/project_config.proto).
Example:
[nodir's bucket in cr-buildbucket-dev](https://chromium.googlesource.com/infra/experimental/+/da2edaf070a2211451289be0baf3bc74bd204a0a/cr-buildbucket-dev.cfg#27).

### Per buildbucket instance

Luci-config file
[services/\<appid\>:swarming_task_template.json][swarming_task_template.json]
specifies the body of POST request that buildbucket sends to swarming when
creating a task.

It contains the isolate and command line parameters. In general, you can
specify anything you want, but to run a recipe, see [Kitchen](#using-kitchen).

#### Parameters

The template may contain parameters of form `$name` in string literals.
They will be expanded during task scheduling. Known parameters:

* bucket: value of build.bucket.
* builder: value of `builder_name` build parameter.
* repository: repository URL of the recipe. Taken from the bucket config.
* revision: revision of the recipe, the value of `swarming.recipe.revision`
  build parameter.
  For example: `"swarming": {"recipe": {"revision": "deadbeef" } }`
* recipe: name of the recipe. Taken from the bucket config.
* properties-json: JSON string containing "properties" build paramter.

Example: [swarming_task_template.json].

## Tags

Swarming tasks created by buildbucket have extra tags:

* `buildbucket_hostname:<hostname>`
* `buildbucket_bucket:<bucket>`
* `recipe_repository:<repo url>`
* `recipe_revision:<revision>`
* `recipe_name:<name>`
* all tags in `common_swarming_tags` of swarming config.
* all tags in `swarming_tags` of builder config.
* all tags in build creation request.

Buildbucket builds associated with swarming tasks have extra tags:

* `swarming_hostname:<hostname>`
* `swarming_task_id:<task_id>`
* `swarming_tag:<tag>` for each swarming task tag.
* `swarming_dimension:<dimension>` for each dimension.

## Using kitchen

[Kitchen][kitchen]
is a Go binary that can fetch a repository, checkout a specific
revision and run a recipe.

    kitchen cook \
      -repository https://chromium.googlesource.com/chromium/tools/build \
      -revision deadbeef1 \
      -recipe myrecipe \
      -properties '{"mastername": "client.v8", "slavename": "vm1-m1"}'

This command will clone/fetch
https://chromium.googlesource.com/chromium/tools/build
checkout revision `deadbeef1`, parse `infra/config/recipes.cfg`,
find `recipes.py` and run recipe `myrecipe`.


### Task entry point

Kitchen is designed to be an entry point of swarming tasks because it has
minimum runtime dependencies: git to checkout a repository and python to run
recipes.

### Isolation

[isolate_kitchen.py] cross-compiles kitchen for 6 platforms, isolates them,
pushes to the isolate server and prints an isolate hash.
You can use the isolate hash in
[swarming_task_template.json][swarming_task_template.json] file.

## Life of a swarming build

1. A user schedules a build on bucket `"foobar"` configured as above.
   The build has `"builder_name": "Linux-Release"` parameter.
1. Linux-Release config is matched. This is a build for swarming.
1. Task template is rendered. Repository URL, recipe and other parameters
   are expanded to "https://chromium.googlesource.com/chromium/tools/build",
   "chromium", etc.
1. Swarming task is created.
1. Build entity is mutated to have extra tags, to point to the task,
   is marked as STARTED and saved.
1. Swarming task starts. Kitchen starts, clones repository, runs "chromium"
   recipe.
1. Swarming task completes. Swarming sends a message to buildbucket via PubSub.
1. Buildbucket receives the message and marks the build as complete.

Note: swarming does not notify on task start, so buildbucket marks builds as
STARTED right after creation.

[kitchen]: https://github.com/luci/recipes-py/tree/master/go/cmd/kitchen
[isolate_kitchen.py]: https://github.com/luci/recipes-py/blob/master/go/cmd/kitchen/isolate_kitchen.py
[swarming_task_template.json]: https://chrome-internal.googlesource.com/infradata/config/+/master/configs/cr-buildbucket/swarming_task_template.json
