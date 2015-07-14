# Buildbucket service

Buildbucket is a build queue in the cloud. Chromium CQ schedule tryjobs on
buildbucket. Buildbot masters poll build buckets, create build requests,
and report back on results. CQ reads build status from buildbucket.

*  __Location__: [cr-buildbucket.appspot.com](https://cr-buildbucket.appspot.com)
*  __Documentation__: [cr-buildbucket.appspot.com](https://cr-buildbucket.appspot.com)
*  __Design doc__: [go/buildbucket-design](http://go/buildbucket-design)
*  __Source code__: [server](../appengine/cr-buildbucket),
  [buildbot integration](https://chromium.googlesource.com/chromium/tools/build/+/master/scripts/master/buildbucket/)
*  __Configuration__: [chromium](https://chromium.googlesource.com/chromium/src/+/master/infra/project-config/cr-buildbucket.cfg),
  [v8](https://chromium.googlesource.com/v8/v8/+/master/infra/project-config/cr-buildbucket.cfg),
  _your repo_.
*  __Point of contact__: nodir@
