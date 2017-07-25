# Cloud SQL Helper

`cloudsqlhelper` is a wrapper around
[Cloud SQL Proxy](https://cloud.google.com/sql/docs/mysql/sql-proxy) and
[migrate](https://github.com/mattes/migrate) schema migration tool, intended for
use with Google Cloud SQL DBs (Second Generation).

It helps with versioning and maintaining of MySQL database schemas, across
multiple environments (dev, staging, prod) and many developers. Its main
purpose is to streamline the development process of services that use Cloud SQL
and have fast, multi-staged release cycle (dev -> staging -> prod).

It assumes a process in which all DB schema changes are executed as separate
incremental SQL statements. Such statements are versioned (and committed into
the repository), and they travel through the release pipeline, along with the
code. It means a schema change hits production only after it (in its very
exact SQL form) has been validated to work in development and staging
environments.

**It means you'll need to know SQL to successfully write new migrations!**

For more information of what schema migrations are and why they are needed:
- [Wikipedia page](https://en.wikipedia.org/wiki/Schema_migration)
- [Database migrations done right](http://www.brunton-spall.co.uk/post/2014/05/06/database-migrations-done-right/)
- [Evolutionary database design](https://martinfowler.com/articles/evodb.html)

## Prerequisites

In order to successfully use `cloudsqlhelper` you'll need:
- [Google Cloud SDK](https://cloud.google.com/sdk/)
- [cloud_sql_proxy](https://cloud.google.com/sql/docs/mysql/sql-proxy) in `PATH`

After getting the SDK, set Application Default Credentials to self by running:

```shell
gcloud auth application-default login --no-launch-browser
```

This command tells Cloud SQL Proxy what credentials (yours) to use when
connecting to Cloud SQL.

## General operations

Almost all `cloudsqlhelper` subcommands expect a configuration file `dbs.yaml`,
located in the current directory. It specifies known databases (e.g dev,
staging, prod), and how to connect to them (see the full example below). For
internal projects (that aren't expected to be forked), it is fine to commit this
config file into the repository. It doesn't contain any secret information.

Similarly, subcommands that operate with migrations expect migration SQL scripts
to be located in `./migrations/` directory. These scripts define how to migrate
database schema "up" (when rolling out new changes) and "down" (when rolling
back changes, e.g. if they are bad). This directory should be committed into the
repository as well, since it essentially contains the history of schema changes.

The simplest way to use the tool is to setup a separate per-project directory
with `dbs.yaml` config and `migrations` directory, and then `cd` into it
whenever calling any `cloudsqlhelper` subcommands. It is also possible to
explicitly specify where `dbs.yaml` and `migrations` are via `-config` and
`-migrations` flags.

Finally, almost all subcommands need to know what exact instance of database
they should target (dev, staging, prod, etc, as defined in `dbs.yaml`).
This can be specified via `-db` flag, the default value is "dev" (local database
used for development).

## Tutorial

Let's assume there's some existing project that uses `cloudsqlhelper` for DB
migrations, and we want to setup a local DB with up-to-date schema, tinker with
it, and finally commit some schema change.

We also assume `cloudsqlhelper` is in `PATH`.

```shell
# Assume dbs.yaml is in 'sql' subdirectory. It can be anywhere else, this is not
# essential, we just need to cd into the directory with dbs.yaml.
> cd my_cool_project/sql

# Attempt to apply all schema changes (committed in the repo) to our dev DB.
> cloudsqlhelper migrate-up
...
[E2017-07-11T20:20:20.537020-07:00 91791 0 main.go:85] Failed - Error 1049: Unknown database 'dev-myname'
...

# It failed! Database doesn't exist yet.

# Create the dev database then. This is needed only for the very first time.
> cloudsqlhelper create-db

# Apply all schema changes again.
> cloudsqlhelper migrate-up
...
[I2017-07-11T20:25:01.325401-07:00 91868 0 migrations.go:30] migrate: 1/u init (717.936141ms)
[I2017-07-11T20:25:01.404131-07:00 91868 0 main.go:132] Changes applied!
[I2017-07-11T20:25:01.444376-07:00 91868 0 migrations.go:140] Current version: 1
...

# Success! There was only 1 migration there in this case.

# Now we want to browse around the database using our favorite MySql client.
# For that we need a database socket to connect to. Let's launch cloud_sql_proxy
# configured to connect to the dev db (default).
> cloudsqlhelper proxy
2017/07/11 20:26:56 Listening on /var/tmp/cloud-sql/cloud-project-dev:us-central1:sql-db-dev ...
2017/07/11 20:26:56 Ready for new connections

# And it blocks like that, waiting for connections on local Unix socket.
# Go ahead and connect to it (the one in /var/tmp/...), using appropriate
# username and password (if any). No need to use SSL, since the proxy implements
# encryption and authentication already. This socket can also be used from GAE
# apps running locally on dev_server.

# Hit Ctrl+C to close the proxy. Or switch to a different terminal and proceed
# there. All `cloudsqlhelper` commands either start a new proxy each time, or
# detect and use existing instance of the proxy (and so it's fine to have it
# running in background). Proxy reuse happens only if "local_socket" is
# configured in dbs.yaml. Do not configure it for prod DB, having a long-living
# local socket connected to prod DB is not good.

# Let's write a new migration that adds a new table named 'stuff'. We start by
# preparing two empty *.sql files: one for "up" migration, another for "down".
# The "down" one should be reverse of "up" one. It will be used to rollback the
# change if something blows up.
> cloudsqlhelper create-migration
Enter a name for the new migration:
> add_stuff_table
Created /.../my_cool_project/sql/migrations/002_add_stuff_table.up.sql
Created /.../my_cool_project/sql/migrations/002_add_stuff_table.down.sql
Populate these files with SQL statements to migrate schema up (for roll-forwards)
and down (for roll-backs). Test locally that migrations apply in both directions!

# You'll notice that new migration has a sequence number (002 in this case).
# When updating a DB, migrations are execution sequentially one after another.

# Let's now edit the placeholder files. Open 002_add_stuff_table.up.sql and
# append the following SQL there:
CREATE TABLE stuff (
  id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(255)
);

# And in 002_add_stuff_table.down.sql should be the reverse action:
DROP TABLE stuff;

# Testing roll-forward.
> cloudsqlhelper migrate-up
...
[I2017-07-11T20:58:00.823761-07:00 92897 0 migrations.go:140] Current version: 1
[I2017-07-11T20:58:01.666427-07:00 92897 0 migrations.go:30] migrate: 2/u add_stuff_table (720.742503ms)
[I2017-07-11T20:58:01.745257-07:00 92897 0 main.go:132] Changes applied!
[I2017-07-11T20:58:01.785451-07:00 92897 0 migrations.go:140] Current version: 2
...

# Testing roll-back.
> cloudsqlhelper migrate-down
...
[I2017-07-11T20:58:39.184158-07:00 92902 0 migrations.go:140] Current version: 2
[I2017-07-11T20:58:40.007436-07:00 92902 0 migrations.go:30] migrate: 2/d add_stuff_table (702.85814ms)
[I2017-07-11T20:58:40.087916-07:00 92902 0 main.go:144] Changes applied!
[I2017-07-11T20:58:40.129116-07:00 92902 0 migrations.go:140] Current version: 1
...

# Works both ways!

# If something breaks in a non-trivial way during this process, you may manually
# attempt to fix the schema to previous state and then force-set the version via
# 'cloudsqlhelper force-version 1' (1 because it's the version we started from).
#
# It might be also simpler to just redo the database from scratch (this is fine
# for local development DB):
> cloudsqlhelper drop-db
> cloudsqlhelper create-db
> cloudsqlhelper migrate-up

# Let's commit this migration. There should be 3 files total: two SQL scripts
# and 'last_version' pointer.
> git add migrations
> git status migrations/
...
  new file:   migrations/002_add_stuff_table.down.sql
  new file:   migrations/002_add_stuff_table.up.sql
  modified:   migrations/last_version

# Send for review, commit.

# Now that the change is committed, we want to deploy it to the staging server,
# to verify it works in an environment that is closer to the production one.
#
# We execute exact same 'migrate-up' command, but target 'staging' database
# instead.

> cloudsqlhelper migrate-up -db staging
...
[I2017-07-11T21:09:12.659364-07:00 93737 0 migrations.go:140] Current version: 1
[I2017-07-11T21:09:12.539868-07:00 93737 0 migrations.go:30] migrate: 2/u add_stuff_table (1.233254463s)
[I2017-07-11T21:09:12.618837-07:00 93737 0 main.go:132] Changes applied!
[I2017-07-11T21:09:12.659364-07:00 93737 0 migrations.go:140] Current version: 2
...
```

## Example of dbs.yaml config

See the source code (`config.go`) for more details.

```yaml
databases:

# Per-developer DBs for local development and tinkering. Assumes each developer
# connects to single shared Cloud SQL instance as 'root' (passwordless), and
# uses their own 'dev-<user>' DB. The proxy socket is located at predefined
# path, so various localhost tools (like mysql client or GAE dev server) can
# easily connect to it.
- id: dev
  user: root
  db: dev-${user}
  # This is "Instance connection name" from Cloud Console. You should have at
  # least "Cloud SQL Client" role in this project.
  cloud_sql_instance: cloud-project-dev:us-central1:sql-db-dev
  # Due to how cloud_sql_proxy works, 'local_socket' name must end with instance
  # connection name too. By using 'local_socket' we assign a stable name to the
  # socket, so it can be referenced in various local scripts.
  local_socket: /var/tmp/cloud-sql/cloud-project-dev:us-central1:sql-db-dev

# Single staging database shared by all developers, in the same cloud project.
- id: staging
  user: root
  db: staging
  cloud_sql_instance: cloud-project-dev:us-central1:sql-db-dev

# Production instance. Requires password, as a reminder that touching it is
# a big deal. Note that the primary authentication layer is still Cloud IAM
# (it's handled by cloud_sql_proxy), so the password is mostly a precaution.
- id: prod
  user: root
  db: prod
  cloud_sql_instance: cloud-project-prod:us-central1:sql-db-prod
  require_password: true
```
