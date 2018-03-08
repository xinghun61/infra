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
	"go.chromium.org/luci/auth/identity"
	"go.chromium.org/luci/common/clock"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/server/auth"

	gr "golang.org/x/build/gerrit"
	"golang.org/x/net/context"

	"google.golang.org/appengine"

	"infra/tricium/api/v1"
	"infra/tricium/appengine/common"
	"infra/tricium/appengine/common/config"
)

// The timestamp format used by Gerrit (using the reference date).
// All timestamps are in UTC.
const timeStampLayout = "2006-01-02 15:04:05.000000000"

// Status field values in a Gerrit FileInfo struct.
// See Gerrit API docs: https://goo.gl/ABFHDg
// This list is not exhaustive.
const (
	fileStatusAdded    = "A"
	fileStatusDeleted  = "D"
	fileStatusModified = "M"
)

// Project tracks the last poll of a Gerrit project.
//
// Mutable entity.
// LUCI datastore ID (=string on the form host:project) field.
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
// This function will be called periodically by a cron job, but may also be
// invoked directly. That is, it may run concurrently and two parallel runs may
// query Gerrit using the same last poll. This scenario would lead to duplicate
// tasks in the service queue. This is OK because the service queue handler
// will check for existing active runs for a change before moving tasks further
// along the pipeline.
func poll(c context.Context, gerrit API, cp config.ProviderAPI) error {
	sc, err := cp.GetServiceConfig(c)
	if err != nil {
		return fmt.Errorf("failed to get service config: %v", err)
	}
	var ops []func() error
	for _, pd := range sc.Projects {
		triciumProject := pd.GetName()
		details := pd.GetGerritDetails()
		if details != nil {
			ops = append(ops, func() error {
				return pollProject(c, triciumProject, details, gerrit)
			})
		}
	}
	return common.RunInParallel(ops)
}

// pollProject polls for changes for one Gerrit project.
//
// Each poll to a Gerrit host and project is logged with a timestamp and last
// seen revisions (within the same second). The timestamp of the most recent
// change in the last poll is used in the next poll, as the value of 'after'
// in the query string. If no previous poll has been logged, then a time
// corresponding to zero is used (time.Time{}).
func pollProject(c context.Context, triciumProject string, gerritDetails *tricium.GerritDetails, gerrit API) error {
	// Get last poll data for the given host/project.
	p := &Project{ID: gerritProjectID(gerritDetails.Host, gerritDetails.Project)}
	if err := ds.Get(c, p); err != nil {
		if err != ds.ErrNoSuchEntity {
			return fmt.Errorf("failed to get Project entity: %v", err)
		}
		logging.Infof(c, "Found no previous entry for id:%s", p.ID)
		err = nil
		p.Instance = gerritDetails.Host
		p.Project = gerritDetails.Project
	}

	// If no previous poll, store current time and return.
	if p.LastPoll.IsZero() {
		logging.Infof(c, "No previous poll for %s/%s. Storing current timestamp and stopping.",
			gerritDetails.Host, gerritDetails.Project)
		p.ID = gerritProjectID(gerritDetails.Host, gerritDetails.Project)
		p.Instance = gerritDetails.Host
		p.Project = gerritDetails.Project
		p.LastPoll = clock.Now(c).UTC()
		logging.Debugf(c, "Storing project data: %+v", p)
		if err := ds.Put(c, p); err != nil {
			return fmt.Errorf("failed to store Project entity: %v", err)
		}
		return nil
	}

	logging.Infof(c, "Last poll: %+v", p)

	// TODO(emso): Add a limit for how many entries that will be processed
	// in a poll. If, for instance, the service is restarted after some
	// down time, all changes since the last poll before the service went
	// down will be processed. Too many changes to process could cause the
	// transaction to fail due to the number of entries touched. A failed
	// transaction will cause the same poll pointer to be used at the next
	// poll, and the same problem will happen again.

	// Query for changes updated since last poll. Account for the fact
	// that results may be truncated and we may need to send several
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
	// This is used to move the poll pointer forward and avoid polling for
	// the same changes more than once. There may still be an overlap but
	// the tracking of change state should be update between polls (and is
	// also guarded by a transaction).
	sort.Sort(sort.Reverse(byUpdatedTime(changes)))

	// Extract updates.
	diff, uchanges, dchanges, err := extractUpdates(c, p, changes)
	if err != nil {
		return fmt.Errorf("failed to extract updates: %v", err)
	}

	// Store updated tracking data.
	if err := ds.RunInTransaction(c, func(c context.Context) error {
		ops := []func() error{
			// Update existing changes and add new ones.
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
	return enqueueAnalyzeRequests(c, triciumProject, gerritDetails, diff)
}

// extractUpdates extracts change updates.
//
// Compares stored tracking of changes and those found in the poll. Returns
// the change diff list to convert to Analyze requests, the list of tracked
// changes to update, and then the list of tracked changes to remove.
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
	// TODO(emso): Consider depending on the order provided by datastore.
	// That is, depend on keys and values being in the same order from Get.
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
			// Note that we are only adding keys for entries
			// already present in the datastore to the delete list.
			// That is, we should not get any NoSuchEntity errors.
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
func enqueueAnalyzeRequests(ctx context.Context, triciumProject string, gerritDetails *tricium.GerritDetails, changes []gr.ChangeInfo) error {
	logging.Debugf(ctx, "Enqueue Analyze requests for %d changes", len(changes))
	if len(changes) == 0 {
		return nil
	}
	owners := map[string]bool{}
	checkWhitelist := true
	for _, g := range gerritDetails.WhitelistedGroup {
		if g == "*" {
			checkWhitelist = false
			break
		}
	}
	var tasks []*tq.Task
	for _, c := range changes {
		if checkWhitelist {
			if len(gerritDetails.WhitelistedGroup) == 0 {
				logging.Errorf(ctx, "No whitelisted groups, not enqueuing tasks")
				continue
			}
			whitelisted, ok := owners[c.Owner.Email]
			if !ok {
				ident, err := identity.MakeIdentity("user:" + c.Owner.Email)
				if err != nil {
					logging.Errorf(ctx, "Failed to create identity for %s, err: %v", c.Owner.Email, err)
					// If we fail to create the identity
					// for a user, skip this user for the
					// rest of this poll.
					owners[c.Owner.Email] = false
					continue
				}
				authOK, err := auth.GetState(ctx).DB().IsMember(ctx, ident, gerritDetails.WhitelistedGroup)
				if err != nil {
					logging.Errorf(ctx, "Failed to check auth for %s, err: %v", c.Owner.Email, err)
				}
				whitelisted = authOK
				owners[c.Owner.Email] = whitelisted
			}
			if !whitelisted {
				logging.Infof(ctx, "Owner is not whitelisted, not triggering Analyze (owner: %s, project: %s)",
					c.Owner.Email, gerritDetails.Project)
				continue
			}
		}
		var paths []string
		for k, v := range c.Revisions[c.CurrentRevision].Files {
			if v.Status != fileStatusDeleted {
				paths = append(paths, k)
			}
		}
		if len(paths) == 0 {
			logging.Infof(ctx, "Not making Analyze request for change %s; changes has no files", c.ID)
			continue
		}
		// Sorting files to account for random enumeration in go maps.
		// This is to get consistent behavior for the same input.
		sort.Strings(paths)
		req := &tricium.AnalyzeRequest{
			Project:  triciumProject,
			GitRef:   c.Revisions[c.CurrentRevision].Ref,
			Paths:    paths,
			Consumer: tricium.Consumer_GERRIT,
			GerritDetails: &tricium.GerritConsumerDetails{
				Host:     gerritDetails.Host,
				Project:  gerritDetails.Project,
				Change:   c.ID,
				Revision: c.Revisions[c.CurrentRevision].Ref,
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
// a Gerrit host and project.
func gerritProjectID(host, project string) string {
	return fmt.Sprintf("%s:%s", host, project)
}
