# Buildbucket

Buildbucket is a generic build queue. A build requester can schedule a build
and wait for a result. A building system, such as Swarming, can lease it, build
it and report a result back.

*   Documentation: [go/buildbucket](http://go/buildbucket).
    TODO(nodir): add a link to exported public doc when available.
*   Original design doc and V1 API documentation: [go/buildbucket-design](http://go/buildbucket-design)
*   Deployments:
    *   Prod: [cr-buildbucket.appspot.com](https://cr-buildbucket.appspot.com) [[API](https://cr-buildbucket.appspot.com/rpcexplorer/services/buildbucket.v2.Builds/)]
    *   Dev: [cr-buildbucket-dev.appspot.com](https://cr-buildbucket-dev.appspot.com) [[API](https://cr-buildbucket-dev.appspot.com/rpcexplorer/services/buildbucket.v2.Builds/)]
*   Bugs: [Infra>Platform>Buildbucket component](https://crbug.com?q=component:Infra>Platform>Buildbucket)
*   Contact: nodir@
