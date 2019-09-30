# How Search Works in Monorail

This document outlines how the search functionality in Monorail that powers the
issue list, issue grid, and burndown chart views works.

## Overview

At a high-level, a search query begins in a user's browser or via an API client
that sends an HTTP request. For example, here's the flow of a request from
the issue list page:

1. HTTP request is sent via <form> or JavaScript on issue list page.
1. Monorail GAE instance (module `default`) handles the request, calls a
   `besearch` instance with search query.
1. The `besearch` GAE instance prepares and executes the MySQL search query
   against the 10 MySQL database replicas, and returns the results.

The code for the `besearch` module is the same as the `default` module. The
`default` module calls the `besearch` module over HTTP. See
[`FrontendSearchPipeline_StartBackendSearchCall`](../search/frontendsearchpipeline.py)
for details on how this call is made.

`besearch` is a separate GAE module so that the CPU-intensive processing of
search results does not take up resources on GAE instances that might otherwise
be serving other user-facing requests.

## Sharding

To reduce load on any one MySQL replica, queries are sharded. This means for
every issue query, Monorail executes 10 SQL queries, one for each database
replica. Each query is responsible for fetching 1/10th of the issues. All of
the results are merged in memory in the `besearch` instance.

Knowing which issues to fetch is accomplished using the columns `Issue.shard`
or `IssueSnapshot.shard`.  The value of the `shard` columns is always set to
`issue_id % 10`. So for instance, the SQL query sent to `replica-g2-05` will
include `WHERE Issue.shard = 5` and will only return issues whose ID ends in
`5`.

## Snapshots

To power the burndown charts feature, every issue create and update operation
writes a new row to the `IssueSnapshot` table. When a user visits a chart page,
the search pipeline runs a `SELECT COUNT` query on the `IssueSnapshot` table,
instead of what it would normally do, running a `SELECT` query on the `Issue`
table.

Any given issue will have many snapshots over time. The way we keep track of
the most recent snapshots are with the columns `IssueSnapshot.period_start`
and `IssueSnapshot.period_end`.

If you imagine a Monorail instance with only one issue, each time we add
a new snapshot to the table, we update the previous snapshot's `period_end`
and the new snapshot's `period_start` to be the current unix time. This means
that for a given range (period_start, period_end), there is only one snapshot
that applies. The most recent snapshot always has its period_end set to
MAX_INT.

    Snapshot ID:  1         2         3                 MAX_INT

    Unix time:
    1560000004                        +-----------------+
    1560000003              +---------+
    1560000002    +---------+

