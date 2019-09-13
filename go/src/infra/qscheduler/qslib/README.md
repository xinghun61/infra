# QuotaScheduler

This source tree implements the QuotaScheduler algorithm.

The algorithm is similar to the [Token Bucket](https://en.wikipedia.org/wiki/Token_bucket) algorithm.

- A number of accounts are defined.
- Each account has a quota recharge rate, defined over multiple priority levels.
- Tasks belong to a particular account, and are prioritized based on the account's balance (i.e. they are given a priority corresponding to the best priority with positive quota for that account).
- If the scheduler is configured with preemption enabled, tasks of higher priority may preempt lower-priority ones (and reimburse spent quota from the preempter's account).

In addition to Token Bucket, QuotaScheduler supports features directly related to the ChromeOS Test Lab's needs. In particular:
- Tasks are preferentially assigned to workers that already have matching "provisionable labels" (i.e. installable dependencies).
- Accounts can specify a maximum parallelism, beyond which tasks will not run concurrently.

Code layout:
- `profiler`    Performance profiling tool and simulator for quotascheduler algorithm.
- `protos`      Internal proto definitions, for serializing scheduler state.
- `reconciler`  Caching/queueing logic between swarming (which makes task- or worker- bound calls to this library) and scheduler logic (which uses a global scheduling pass on each scheduling run).
- `scheduler`   Core QuotaScheduler algorithm.
- `tutils`      Convenience library to casting proto timestamps.