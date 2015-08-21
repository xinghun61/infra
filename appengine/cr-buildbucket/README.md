# Buildbucket

[go/buildbucket]

Buildbucket is a generic build queue. A build requester can schedule a build
and wait for a result. A building system, such as Buildbot, can lease it, build
it and report a result back.

*   [Documentation](doc/index.md)
*   Design doc: [go/buildbucket-design], explains API.
*   Deployments:
    *   Prod: [cr-buildbucket.appspot.com](https://cr-buildbucket.appspot.com)
    *   Test: [cr-buildbucket-test.appspot.com](https://cr-buildbucket-test.appspot.com)
    *   Dev: [cr-buildbucket-dev.appspot.com](https://cr-buildbucket-dev.appspot.com)
*   Bugs: [Infra-BuildBucket label](https://crbug.com?q=label=Infra-Buildbucket)
*   Owner: nodir@

## Buildbot

Buildbucket is integrated with buildbot. You can schedule, cancel, search for
buildbot builds and check their results using buildbucket API.

[go/buildbucket-design]: http://go/buildbucket-design
[go/buildbucket]: http://go/buildbucket

## See also

* [FAQ](doc/faq.md)
