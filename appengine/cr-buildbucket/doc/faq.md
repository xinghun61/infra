# Buildbucket FAQ

## How to create a new bucket?

1.  Make sure your repository is
    [registered](/doc/users/services/luci-config/faq.md#How-to-register-a-project).
2.  Create `cr-buildbucket.cfg` file in `infra/config` branch
    ([schema](http://luci-config.appspot.com/schemas/projects:buildbucket.cfg),
    [example](https://chromium.googlesource.com/chromium/src/+/infra/config/cr-buildbucket.cfg))
3.  Wait for ~10 min.
4.  Call [buildbucket.peek] with the bucket to ensure bucket exists and you have
    access. It should return HTTP 200.

## Where ACL groups are defined?

On [auth service](/doc/users/services/auth/index.md)

[buildbucket.peek]: https://cr-buildbucket.appspot.com/_ah/api/explorer/#p/buildbucket/v1/buildbucket.peek
