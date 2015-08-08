# Buildbucket

Buildbucket is a generic build queue. A build requester can schedule a build
and wait for a result. A building system, such as Buildbot, can lease it, build
it and report a result back.

*   [Documentation](doc/index.md)
*   Design doc: [go/buildbucket-design]
*   Deployments:
    *   Prod: [cr-buildbucket.appspot.com](https://cr-buildbucket.appspot.com)
    *   Test: [cr-buildbucket-test.appspot.com](https://cr-buildbucket-test.appspot.com)
    *   Dev: [cr-buildbucket-dev.appspot.com](https://cr-buildbucket-dev.appspot.com)
*   Bugs: [Infra-BuildBucket label](https://crbug.com?q=label=Infra-Buildbucket)
*   Owner: nodir@

[go/buildbucket-design]: http://go/buildbucket-design
