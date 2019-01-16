# I made a change here, but my infra(_internal) code importing infra_libs doesn't see it!

Follow this:
1. Land your CL changing packages/* first.

1. Create & land another CL bumping version number
([example](https://chromium-review.googlesource.com/1237046)).
It's important to keep it separate CL such that it is never reverted.

1. Watch gsubtreed-ed repo populated with your change and version bump:
   * [infra/infra/packages/dataflow](https://chromium.googlesource.com/infra/infra/packages/dataflow)
   * [infra/infra/packages/infra_libs](https://chromium.googlesource.com/infra/infra/packages/infra_libs)

1. Find the hash of corresponding version bumping commit.
   (e.g., [`0655bac8c4634b473040cfd80edd9e43f0997499`](https://chromium.googlesource.com/infra/infra/packages/infra_libs/+/0655bac8c4634b473040cfd80edd9e43f0997499)).
   NOTE: this hash will almost certainly be different than the hash of
   the commit you landed in `infra/infra` repo.

1. Now that you know (version, hash) tuple, bump the pin in [`bootstrap/deps.pyl`](../bootstrap/deps.pyl) by
   following
   [rolling-the-version-of-wheel](../bootstrap/README.md#rolling-the-version-of-wheel).
   It sometimes doesn't work from the first try, but at least CQ dry run can test it
   for you. ([example
   CL](https://chromium-review.googlesource.com/c/infra/infra/+/1289007))

1. And if you import infra_libs in infra_internal repo, you'll also need to roll infra
   to infra_internal ([example](https://crrev.com/i/795199)), yes, manually :(
