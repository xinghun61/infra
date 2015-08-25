# crdocs - documentation search.

Crawls .md files in
[registered repositories](https://chrome-internal.googlesource.com/infradata/config/+/master/configs/luci-config/projects.cfg)
and provides full-text search.

The search is powered by [Appengine Search](https://cloud.google.com/appengine/docs/python/search/).

If a repo was not crawled before, scans it entirely looking for .md files.
Otherwise, loads a patchset since last scan and incrementally updates the search
index.

## Access control

Access control is simple, crude, coarse and hard-codeded: .md files hosted on
chromium.googlesource.com are available to anyone. Everything else is available
only to googlers.

## Limitations

Current limitations (can be lifted):

* Access control is coarse, see above
* Crawls only HEAD ref, which is typically refs/heads/master

## Implementation details of index maintenance

For each git ref that needs to be indexed, the cron job checks the latest commit
(`gitiles.get_log`) and compares to its own state (`Ref.indexed_revision`). If
the revisions are different and indexing is not in the process, the job
transactionally records the target revision (Ref.indexing_revision) and enqueues
a push task (`_task_update`) to start indexing. For any indexed Ref that is no
longer in the list, `None` target ref is recorded.

The indexing task (_task_update) first determines how the search index must be
updated. There are two modes: full-rescan and incremental.

### Incremental update

If the both current revision and target revision are known and the task was able
to load a diff from gitiles, it updates only added/modified/deleted .md files.
This is incremental update and it is fast.

### Full rescan

Sometimes incremental update is not possible:

* First time indexing
* A ref needs to be deleted
* Force-push was done on the ref

In this case a full-rescan is done. First, any existing search documents
originating from this ref are deleted. Then, if target commit is specified, a
new push task (`_task_add_all`) to add all new files is enqueued. It is a
separate task because we don't want to delete indexed docs on task retry.
Instead, we want to continue adding files.

The _task_add_all task uses `gitiles.get_tree` to crawl entire tree, in pre-
order, serial way. It is done serially to be able to reliably save last indexed
path and continue if task fails. Task failues happen quite often because of
Gitiles quota shortage. The approach guarantees to eventually index everything.

Crawling a repo serially may look slow, but in fact it exhausts one-hour gitiles
quota in ~1 minute. Anyway, crawling of a tree recursively using
`gitiles.get_tree` is slow and quota-expensive. Gerrit team suggested to provide
an endpoint to list a tree recursively. When this is done, `_task_add_all` can
be updated.
