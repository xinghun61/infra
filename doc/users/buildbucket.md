# Buildbucket service

Buildbucket is a build queue in the cloud. Chromium CQ schedule tryjobs on
buildbucket. Buildbot masters poll build buckets, create build requests,
and report back on results. CQ reads build status from buildbucket.

* **Location**: [cr-buildbucket.appspot.com](https://cr-buildbucket.appspot.com)
* **Documentation**: [cr-buildbucket.appspot.com](https://cr-buildbucket.appspot.com)
* **Design doc**: [go/buildbucket-design](http://go/buildbucket-design)
* **Source code**: [server](../appengine/cr-buildbucket),
  [buildbot integration](https://chromium.googlesource.com/chromium/tools/build/+/master/scripts/master/buildbucket/)
* **Configuration**: [chromium](https://chromium.googlesource.com/chromium/src/+/master/infra/project-config/cr-buildbucket.cfg),
  [v8](https://chromium.googlesource.com/v8/v8/+/master/infra/project-config/cr-buildbucket.cfg),
  _your repo_.
* **Point of contact**: nodir@
