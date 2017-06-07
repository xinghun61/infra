# Buildbucket

[go/buildbucket]

Buildbucket is a generic build queue. A build requester can schedule a build
and wait for a result. A building system, such as Buildbot, can lease it, build
it and report a result back.

*   [Documentation](doc/index.md)
*   Design doc: [go/buildbucket-design], explains API.
*   Deployments:
    *   Prod: [cr-buildbucket.appspot.com](https://cr-buildbucket.appspot.com) [[API](https://cr-buildbucket.appspot.com/_ah/api/explorer)]
    *   Test: [cr-buildbucket-test.appspot.com](https://cr-buildbucket-test.appspot.com) [[API](https://cr-buildbucket-test.appspot.com/_ah/api/explorer)]
    *   Dev: [cr-buildbucket-dev.appspot.com](https://cr-buildbucket-dev.appspot.com) [[API](https://cr-buildbucket-dev.appspot.com/_ah/api/explorer)]
*   Bugs: [Infra>Platform>BuildBucket component](https://crbug.com?q=component:Infra>Platform>Buildbucket)
*   Owner: nodir@

## Swarmbucket

Buildbucket has native integration with Swarming and Recipes.
A bucket can define builders and a buildbucket build in such bucket is converted
to a swarming task that runs a recipe.
The results are reported back to buildbucket when the task completes.
See [Swarming](doc/swarming.md).

## Buildbot

Buildbucket is integrated with buildbot. You can schedule, cancel, search for
buildbot builds and check their results using buildbucket API.

[go/buildbucket-design]: http://go/buildbucket-design
[go/buildbucket]: http://go/buildbucket

## See also

* [FAQ](doc/faq.md)
