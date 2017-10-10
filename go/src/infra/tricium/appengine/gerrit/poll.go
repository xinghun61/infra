// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package gerrit

import (
	"fmt"
	"sort"
	"time"

	"github.com/golang/protobuf/proto"
	ds "go.chromium.org/gae/service/datastore"
	tq "go.chromium.org/gae/service/taskqueue"
	"go.chromium.org/luci/common/clock"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/logging"

	gr "golang.org/x/build/gerrit"
	"golang.org/x/net/context"

	"google.golang.org/appengine"

	"infra/tricium/api/v1"
	"infra/tricium/appengine/common"
	"infra/tricium/appengine/common/config"
)

// The timestamp format used by Gerrit (using the reference date). All timestamps are in UTC.
const timeStampLayout = "2006-01-02 15:04:05.000000000"

// Project tracks the last poll of a Gerrit project.
//
// Mutable entity.
// LUCI datastore ID (=string on the form instance:project) field.
type Project struct {
	ID       string `gae:"$id"`
	Instance string
	Project  string
	// Timestamp of last successful poll.
	LastPoll time.Time
}

// Change tracks the last seen revision for a Gerrit change.
//
// Mutable entity.
// LUCI datastore ID (=fully-qualified Gerrit change ID)
// and parent (=key to GerritProject entity) fields.
type Change struct {
	ID           string  `gae:"$id"`
	Parent       *ds.Key `gae:"$parent"`
	LastRevision string
}

// byUpdateTime sorts changes based on update timestamps.
type byUpdatedTime []gr.ChangeInfo

func (c byUpdatedTime) Len() int           { return len(c) }
func (c byUpdatedTime) Swap(i, j int)      { c[i], c[j] = c[j], c[i] }
func (c byUpdatedTime) Less(i, j int) bool { return c[i].Updated.Time().Before(c[i].Updated.Time()) }

// poll queries Gerrit for changes since the last poll.
//
// Change queries are done on a per project basis for project with configured
// Gerrit details.
//
// This function will be called periodically by a cron job, but may also be invoked
// directly. That is, it may run concurrently and two parallel runs may query Gerrit
// using the same last poll. This scenario would lead to duplicate tasks in the
// service queue. This is OK because the service queue handler will check for exisiting
// active runs for a change before moving tasks further along the pipeline.
func poll(c context.Context, gerrit API, cp config.ProviderAPI) error {
	sc, err := cp.GetServiceConfig(c)
	if err != nil {
		return fmt.Errorf("failed to get service config: %v", err)
	}
	var ops []func() error
	for _, pd := range sc.Projects {
		details := pd.GetGerritDetails()
		if details != nil {
			ops = append(ops, func() error {
				return pollProject(c, pd.Name, details.Host, details.Project, gerrit)
			})
		}
	}
	return common.RunInParallel(ops)
}

// pollProject polls for changes for one Gerrit project.
//
// Each poll to a Gerrit instance and project is logged with a timestamp and
// last seen revisions (within the same second).
// The timestamp of the most recent change in the last poll is used in the next poll,
// (as the value of 'after' in the query string). If no previous poll has been logged,
// then a time corresponding to zero is used (time.Time{}).
func pollProject(c context.Context, triciumProject, instance, gerritProject string, gerrit API) error {
	// Get last poll data for the given instance/project.
	p := &Project{ID: gerritProjectID(instance, gerritProject)}
	if err := ds.Get(c, p); err != nil {
		if err != ds.ErrNoSuchEntity {
			return fmt.Errorf("failed to get Project entity: %v", err)
		}
		logging.Infof(c, "Found no previous entry for id:%s", p.ID)
		err = nil
		p.Instance = instance
		p.Project = gerritProject
	}

	// If no previous poll, store current time and return.
	if p.LastPoll.IsZero() {
		logging.Infof(c, "No previous poll for %s/%s. Storing current timestamp and stopping.",
			instance, gerritProject)
		p.ID = gerritProjectID(instance, gerritProject)
		p.Instance = instance
		p.Project = gerritProject
		p.LastPoll = clock.Now(c).UTC()
		logging.Debugf(c, "Storing project data: %+v", p)
		if err := ds.Put(c, p); err != nil {
			return fmt.Errorf("failed to store Project entity: %v", err)
		}
		return nil
	}
	logging.Infof(c, "Last poll: %+v", p)

	// TODO(emso): Add a limit for how many entries that will be processed in a poll.
	// If, for instance, the service is restarted after some down time all changes since the
	// last poll before the service went down will be processed. To many changes to process could
	// cause the transaction to fail due to the number of entries touched. A failed transaction
	// will cause the same poll pointer to be used at the next poll, and the same problem will
	// happen again.

	// Query for changes updated since last poll.
	// Account for the fact that results may be truncated and we may need to send several
	// queries to get the full list of changes.
	var changes []gr.ChangeInfo
	// Use this counter to skip already seen changes when more than one page
	// of results is requested.
	s := 0
	for {
		chgs, more, err := gerrit.QueryChanges(c, p.Instance, p.Project, p.LastPoll, s)
		if err != nil {
			return fmt.Errorf("failed to query for change: %v", err)
		}
		s += len(chgs)
		changes = append(changes, chgs...)
		// Check if we need to query for more changes, that is, if the
		// results were truncated.
		if !more {
			break
		}
	}

	// No changes found.
	if len(changes) == 0 {
		logging.Infof(c, "Poll done. No changes found.")
		return nil
	}

	// Make sure changes are sorted (most recent change first).
	// This is used to move the poll pointer forward and avoid polling
	// for the same changes more than once. There may still be an overlap
	// but the tracking of change state should be update between polls
	// (and is also guarded by a transaction).
	sort.Sort(sort.Reverse(byUpdatedTime(changes)))

	// Extract updates.
	diff, uchanges, dchanges, err := extractUpdates(c, p, changes)
	if err != nil {
		return fmt.Errorf("failed to extract updates: %v", err)
	}

	// Store updated tracking data.
	if err := ds.RunInTransaction(c, func(c context.Context) error {
		ops := []func() error{
			// Update exisiting changes and add new ones.
			func() error {
				if len(uchanges) == 0 {
					return nil
				}
				return ds.Put(c, uchanges)
			},
			// Delete removed changes.
			func() error {
				if len(dchanges) == 0 {
					return nil
				}
				if err := ds.Delete(c, dchanges); err != nil {
					if me, ok := err.(appengine.MultiError); ok {
						for _, merr := range me {
							if merr != ds.ErrNoSuchEntity {
								// Some error other than entity not found, report.
								return err
							}
						}
					} else {
						return err
					}
				}
				return nil
			},
			// Update poll timestamp.
			func() error {
				p.LastPoll = changes[0].Updated.Time()
				if err := ds.Put(c, p); err != nil {
					return fmt.Errorf("failed to update last poll timestamp: %v", err)
				}
				return nil
			},
		}
		return common.RunInParallel(ops)
	}, &ds.TransactionOptions{XG: true}); err != nil {
		return err
	}
	logging.Infof(c, "Poll done. Processed %d change(s).", len(changes))

	// Convert diff to Analyze requests.
	//
	// Running after the transaction because each seen change will result in one
	// enqueued task and there is a limit on the number of action in a transaction.
	return enqueueAnalyzeRequests(c, triciumProject, diff)
}

// extractUpdates extracts change updates.
//
// Compares stored tracking of changes and those found in the poll.
// Returns the change diff list to convert to Analyze requests, the list of tracked changes to update, and then
// the list of tracked changes to remove.
func extractUpdates(c context.Context, p *Project, changes []gr.ChangeInfo) ([]gr.ChangeInfo, []*Change, []*Change, error) {
	var diff []gr.ChangeInfo
	var uchanges []*Change
	var dchanges []*Change
	// Get list of tracked changes.
	pkey := ds.NewKey(c, "GerritProject", p.ID, 0, nil)
	var trackedChanges []*Change
	for _, change := range changes {
		trackedChanges = append(trackedChanges, &Change{ID: change.ID, Parent: pkey})
	}
	if err := ds.Get(c, trackedChanges); err != nil {
		if me, ok := err.(errors.MultiError); ok {
			for _, merr := range me {
				if merr != nil && merr != ds.ErrNoSuchEntity {
					return diff, uchanges, dchanges, err
				}
			}
		} else if err != ds.ErrNoSuchEntity {
			logging.Errorf(c, "Getting tracked changes failed: %v", err)
			return diff, uchanges, dchanges, err
		}
	}
	// Create map of tracked changes.
	t := map[string]Change{}
	for _, change := range trackedChanges {
		if change != nil {
			t[change.ID] = *change
		}
	}
	// TODO(emso): consider depending on the order provided by datastore, that is, depend
	// on keys and values being in the same order from Get.
	logging.Debugf(c, "Found the following tracked changes: %v", t)
	// Compare polled changes to tracked changes, update tracking and add to the
	// diff list when there is an updated revision change.
	for _, change := range changes {
		tc, ok := t[change.ID]
		switch {
		// For untracked and new/draft, start tracking and add to diff list.
		case !ok && (change.Status == "NEW" || change.Status == "DRAFT"):
			logging.Debugf(c, "Found untracked %s change (%s); tracking.", change.Status, change.ID)
			tc.ID = change.ID
			tc.LastRevision = change.CurrentRevision
			uchanges = append(uchanges, &tc)
			diff = append(diff, change)
		// Untracked and not new/draft, move on to the next change.
		case !ok:
			logging.Debugf(c, "Found untracked %s change (%s); leaving untracked.", change.Status, change.ID)
		// For tracked and merged/abandoned, stop tracking (clean up).
		case change.Status == "MERGED" || change.Status == "ABANDONED":
			logging.Debugf(c, "Found tracked %s change (%s); removing.", change.Status, change.ID)
			// Note that we are only adding keys for entries already present in the
			// datastore to the delete list. That is, we should not get any NoSuchEntity
			// errors.
			dchanges = append(dchanges, &tc)
		// For tracked and unseen revision, update tracking and add to diff list.
		case tc.LastRevision != change.CurrentRevision:
			logging.Debugf(c, "Found tracked %s change (%s) with new revision; updating.", change.Status, change.ID)
			tc.LastRevision = change.CurrentRevision
			uchanges = append(uchanges, &tc)
			diff = append(diff, change)
		default:
			logging.Debugf(c, "Found tracked %s change (%s) with no update; leaving as is.", change.Status, change.ID)
		}
	}
	return diff, uchanges, dchanges, nil
}

// enqueueAnalyzeRequests enqueues Analyze requests for the provided Gerrit changes.
func enqueueAnalyzeRequests(ctx context.Context, project string, changes []gr.ChangeInfo) error {
	logging.Debugf(ctx, "Enqueue Analyze requests for %d changes", len(changes))
	if len(changes) == 0 {
		return nil
	}
	var tasks []*tq.Task
	for _, c := range changes {
		var paths []string
		for k, v := range c.Revisions[c.CurrentRevision].Files {
			if v.Status != "Delete" {
				paths = append(paths, k)
			}
		}
		// Sorting files to account for random enumeration in go maps.
		// This is to get consistent behavior for the same input.
		sort.Strings(paths)
		// TODO(emso): Mapping between Gerrit project name and that used in Tricium?
		req := &tricium.AnalyzeRequest{
			Project:  project,
			GitRef:   c.Revisions[c.CurrentRevision].Ref,
			Paths:    paths,
			Consumer: tricium.Consumer_GERRIT,
			GerritDetails: &tricium.GerritConsumerDetails{
				Project:  project,
				Change:   c.ID,
				Revision: c.CurrentRevision,
			},
		}
		b, err := proto.Marshal(req)
		if err != nil {
			return fmt.Errorf("failed to marshal Analyze request: %v", err)
		}
		t := tq.NewPOSTTask("/internal/analyze", nil)
		t.Payload = b
		logging.Debugf(ctx, "Converted change details (%v) to Tricium request (%v)", c, req)
		tasks = append(tasks, t)
	}
	if err := tq.Add(ctx, common.AnalyzeQueue, tasks...); err != nil {
		return fmt.Errorf("failed to enqueue Analyze request: %v", err)
	}
	return nil
}

// gerritProjectID constructs the ID used to store information about
// a Gerrit instance and project.
func gerritProjectID(instance, project string) string {
	return fmt.Sprintf("%s:%s", instance, project)
}
