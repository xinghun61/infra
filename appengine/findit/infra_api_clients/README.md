# infra\_clients

The [infra\_clients](infra_clients) module is for client libraries that
interacts with APIs of various infra services like buildbucket, Swarming,
Isolate, Reitveld codereview, etc.

It depends on the sibling [libs](libs) and [gae\_libs](gae_libs).

# How to use?

Create symbolic links to [infra\_clients](infra_clients), [gae\_libs](gae_libs)
and [libs](libs) in the same directory PARENT\_DIR, and ensure that PARENT\_DIR
is added to sys.path or PYTHONPATH.

The usage would look like: `from infra_clients import INFRA_SERVICE_API`
