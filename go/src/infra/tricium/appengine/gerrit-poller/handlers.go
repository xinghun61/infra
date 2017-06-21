// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package gerritpoller implements HTTP handlers for the gerrit-poller module.
package gerritpoller

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io/ioutil"
	"net/http"
	"net/url"
	"sort"
	"strconv"
	"time"

	"github.com/golang/protobuf/proto"
	ds "github.com/luci/gae/service/datastore"
	tq "github.com/luci/gae/service/taskqueue"
	"github.com/luci/luci-go/common/logging"
	"github.com/luci/luci-go/server/auth"
	"github.com/luci/luci-go/server/router"

	"golang.org/x/build/gerrit"
	"golang.org/x/net/context"

	"google.golang.org/appengine"

	"infra/tricium/api/v1"
	"infra/tricium/appengine/common"
)

const (
	instance = "https://chromium-review.googlesource.com"
	scope    = "https://www.googleapis.com/auth/gerritcodereview"
	project  = "playground/gerrit-tricium"
)

// The timestamp format used by Gerrit (using the reference date). All timestamps are in UTC.
const timeStampLayout = "2006-01-02 15:04:05.000000000"

// GerritProject tracks the last poll of a Gerrit project.
//
// Mutable entity.
// LUCI datastore ID (=string on the form instance:project) field.
type GerritProject struct {
	ID       string `gae:"$id"`
	Instance string
	Project  string
	// Timestamp of last successful poll.
	LastPoll time.Time
}

// GerritChange tracks the last seen revision for a Gerrit change.
//
// Mutable entity.
// LUCI datastore ID (=changeID) and parent (=key to GerritProject entity) fields.
type GerritChange struct {
	ID           string  `gae:"$id"`
	Parent       *ds.Key `gae:"$parent"`
	LastRevision string
}

// GerritChangeDetails includes information needed to analyse an updated patch set.
type GerritChangeDetails struct {
	Instance        string
	Project         string
	ChangeID        string
	CurrentRevision string
	ChangeURL       string
	GitRef          string
	FileChanges     []FileChangeDetails
}

// FileChangeDetails includes information for a file change.
// The status field corresponds to the FileInfo status field
// used by Gerrit, where "A"=Added, "D"=Deleted, "R"=Renamed,
// "C"=Copied, "W"=Rewritten, and "M"=Modified (same as not set).
type FileChangeDetails struct {
	Path   string
	Status string
}

// FileChangesByPath is used to sort FileChangeDetails lexically on path name.
type FileChangesByPath []FileChangeDetails

func (f FileChangesByPath) Len() int           { return len(f) }
func (f FileChangesByPath) Swap(i, j int)      { f[i], f[j] = f[j], f[i] }
func (f FileChangesByPath) Less(i, j int) bool { return f[i].Path < f[j].Path }

// byUpdateTime sorts changes based on update timestamps.
type byUpdatedTime []gerrit.ChangeInfo

func (c byUpdatedTime) Len() int           { return len(c) }
func (c byUpdatedTime) Swap(i, j int)      { c[i], c[j] = c[j], c[i] }
func (c byUpdatedTime) Less(i, j int) bool { return c[i].Updated.Time().Before(c[i].Updated.Time()) }

func pollHandler(ctx *router.Context) {
	c, w := ctx.Context, ctx.Writer
	if err := poll(c); err != nil {
		logging.WithError(err).Errorf(c, "failed to poll: %v", err)
		w.WriteHeader(http.StatusInternalServerError)
		return
	}
	logging.Debugf(c, "[gerrit-poller] Successfully completed poll")
	w.WriteHeader(http.StatusOK)
}

// poll queries Gerrit for changes since the last poll.
//
// Each poll to a Gerrit instance and project is logged with a timestamp and
// last seen revisions (within the same second).
// The timestamp of the most recent change in the last poll is used in the next poll,
// (as the value of 'after' in the query string). If no previous poll has been logged,
// then a time corresponding to zero is used (time.Time{}).
// This function will be called periodically by a cron job, but may also be invoked
// directly. That is, it may run concurrently and two parallel runs may query Gerrit
// using the same last poll. This scenario would lead to duplicate tasks in the
// service queue. This is OK because the service queue handler will check for exisiting
// active runs for a change before moving tasks further along the pipeline.
func poll(c context.Context) error {
	// TODO(emso): Get project/instance from luci-config
	// Get last poll data for the given instance/project.
	p := &GerritProject{ID: gerritProjectID(instance, project)}
	if err := ds.Get(c, p); err != nil {
		if err != ds.ErrNoSuchEntity {
			return err
		}
		logging.Infof(c, "Found no previous entry for id:%s", p.ID)
		err = nil
		p.Instance = instance
		p.Project = project
	}
	// If no previous poll, store current time and return.
	if p.LastPoll.IsZero() {
		logging.Infof(c, "No previous poll for %s/%s. Storing current timestamp and stopping.",
			instance, project)
		p.ID = gerritProjectID(instance, project)
		p.Instance = instance
		p.Project = project
		p.LastPoll = time.Now()
		logging.Debugf(c, "Storing project data: %+v", p)
		if err := ds.Put(c, p); err != nil {
			return err
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
	var changes []gerrit.ChangeInfo
	// Use this counter to skip already seen changes when more than one page
	// of results is requested.
	s := 0
	for {
		chgs, more, err := queryChanges(c, p, s)
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

	// Store updated project data and enqueue extracted analysis tasks.
	// These operations should happen in a transaction because by storing the
	// project data we assume that all new changes have been enqueued as analysis
	// tasks.
	if err := ds.RunInTransaction(c, func(c context.Context) error {
		// Update tracking of changes, getting back updated changes.
		uc, err := updateTracking(c, p, changes)
		if err != nil {
			return err
		}
		// Update tracking of last poll.
		p.LastPoll = changes[0].Updated.Time()
		if err := ds.Put(c, p); err != nil {
			return err
		}
		// Convert to analysis tasks and enqueue.
		changeDetails := convertToChangeDetails(p, uc)
		return enqueueServiceRequests(c, changeDetails)
	}, nil); err != nil {
		return err
	}
	logging.Infof(c, "Poll done. Processed %d change(s).", len(changes))
	return nil
}

// updateTracking updates the tracking of the given Gerrit project based on the list of
// updated changes. Returns a list of changes where the tracked revision and the current
// revision differ.
func updateTracking(c context.Context, p *GerritProject, changes []gerrit.ChangeInfo) ([]gerrit.ChangeInfo, error) {
	var diff []gerrit.ChangeInfo
	// Get list of tracked changes.
	pkey := ds.NewKey(c, "GerritProject", p.ID, 0, nil)
	var trackedChanges []*GerritChange
	for _, change := range changes {
		trackedChanges = append(trackedChanges, &GerritChange{ID: change.ChangeID, Parent: pkey})
	}
	if err := ds.Get(c, trackedChanges); err != nil {
		if me, ok := err.(appengine.MultiError); ok {
			for _, merr := range me {
				if merr != nil && merr != ds.ErrNoSuchEntity {
					return diff, err
				}
			}
		} else {
			logging.Errorf(c, "Getting tracked changes failed: %v", err)
			return diff, err
		}
	}
	// TODO(emso): consider depending on the order provided by datastore, that is, depend
	// on keys and values being in the same order from GetMulti.
	// Create map of tracked changes.
	t := map[string]GerritChange{}
	for _, change := range trackedChanges {
		if change != nil {
			t[change.ID] = *change
		}
	}
	logging.Debugf(c, "Found the following tracked changes: %v", t)
	// Compare polled changes to tracked changes, update tracking and add to the
	// diff list when there is an updated revision change.
	var uchanges []*GerritChange
	var dchanges []*GerritChange
	for _, change := range changes {
		tc, ok := t[change.ChangeID]
		switch {
		// For untracked and new/draft, start tracking.
		case !ok && (change.Status == "NEW" || change.Status == "DRAFT"):
			logging.Debugf(c, "Found untracked %s change (%s); tracking.", change.Status, change.ChangeID)
			tc.ID = change.ChangeID
			tc.LastRevision = change.CurrentRevision
			uchanges = append(uchanges, &tc)
			diff = append(diff, change)
		// Untracked and not new/draft, move on to the next change.
		case !ok:
			logging.Debugf(c, "Found untracked %s change (%s); leaving untracked.", change.Status, change.ChangeID)
		// For tracked and merged/abandoned, stop tracking (clean up).
		case change.Status == "MERGED" || change.Status == "ABANDONED":
			logging.Debugf(c, "Found tracked %s change (%s); removing.", change.Status, change.ChangeID)
			// Note that we are only adding keys for entries already present in the
			// datastore to the delete list. That is, we should not get any NoSuchEntity
			// errors.
			dchanges = append(dchanges, &tc)
		// For tracked and unseen revision, update tracking and to diff list.
		case tc.LastRevision != change.CurrentRevision:
			logging.Debugf(c, "Found tracked %s change (%s) with new revision; updating.", change.Status, change.ChangeID)
			tc.LastRevision = change.CurrentRevision
			uchanges = append(uchanges, &tc)
			diff = append(diff, change)
		default:
			logging.Debugf(c, "Found tracked %s change (%s) with no update; leaving as is.", change.Status, change.ChangeID)
		}
	}
	// Update stored data.
	ops := []func() error{
		// Update exisiting changes and add new ones.
		func() error {
			return ds.Put(c, uchanges)
		},
		// Delete removed changes.
		func() error {
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
	}
	if err := common.RunInParallel(ops); err != nil {
		return diff, err
	}
	return diff, nil
}

// convertToChangeDetails converts the given list of changes to change details structs.
func convertToChangeDetails(p *GerritProject, changes []gerrit.ChangeInfo) []*GerritChangeDetails {
	var tasks []*GerritChangeDetails
	for _, c := range changes {
		var fc []FileChangeDetails
		files := c.Revisions[c.CurrentRevision].Files
		for k, v := range files {
			fc = append(fc, FileChangeDetails{
				Path:   k,
				Status: v.Status,
			})
		}
		// Sorting files to account for random enumeration in go maps.
		// This is to get consistent behavior for the same input.
		sort.Sort(FileChangesByPath(fc))
		rev := c.Revisions[c.CurrentRevision]
		tasks = append(tasks, &GerritChangeDetails{
			Instance:        instance,
			Project:         c.Project,
			ChangeID:        c.ChangeID,
			CurrentRevision: c.CurrentRevision,
			ChangeURL: fmt.Sprintf("%s/c/%d/%d", p.Instance, c.ChangeNumber,
				rev.PatchSetNumber),
			GitRef:      rev.Ref,
			FileChanges: fc,
		})
	}
	return tasks
}

// queryChanges sends one query for changes to Gerrit using the provided poll data and offset.
// The poll data is assumed to correspond to the last seen change before this poll. Within one
// poll, the offset is used to handle consecutive calls to this function.
// A list of changes is returned in the same order as they were returned by Gerrit.
// The result tuple includes a boolean value to indicate of the result was truncated and
// more queries should be sent to get the full list of changes. For new queries within the same
// poll, this function should be called again with an increased offset.
func queryChanges(c context.Context, p *GerritProject, offset int) ([]gerrit.ChangeInfo, bool, error) {
	var changes []gerrit.ChangeInfo
	// Compose, connect and send.
	url := composeChangesQueryURL(p, offset)
	logging.Infof(c, "Using URL: %s", url)
	req, err := http.NewRequest("GET", url, nil)
	if err != nil {
		return changes, false, err
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Accept", "application/json")
	transport, err := auth.GetRPCTransport(c, auth.AsSelf, auth.WithScopes(scope))
	if err != nil {
		return changes, false, err
	}
	client := http.Client{Transport: transport}
	resp, err := client.Do(req)
	if err != nil {
		return changes, false, err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return changes, false, err
	}
	// Read and convert response.
	body, err := ioutil.ReadAll(resp.Body)
	if err != nil {
		return changes, false, err
	}
	// Remove the magic Gerrit prefix.
	body = bytes.TrimPrefix(body, []byte(")]}'\n"))
	if err = json.Unmarshal(body, &changes); err != nil {
		return changes, false, err
	}
	// Check if changes were truncated.
	more := len(changes) > 0 && changes[len(changes)-1].MoreChanges
	return changes, more, nil
}

// enqueueServiceRequests enqueues service requests for the given change details.
func enqueueServiceRequests(c context.Context, changes []*GerritChangeDetails) error {
	for _, change := range changes {
		req := &tricium.AnalyzeRequest{
			Project: change.Project,
			GitRef:  change.GitRef,
		}
		for _, file := range change.FileChanges {
			if file.Status != "Delete" {
				req.Paths = append(req.Paths, file.Path)
			}
		}
		b, err := proto.Marshal(req)
		if err != nil {
			return fmt.Errorf("failed to marshal Tricium request: %v", err)
		}
		t := tq.NewPOSTTask("internal/analyze", nil)
		t.Payload = b
		if err := tq.Add(c, common.AnalyzeQueue, t); err != nil {
			return fmt.Errorf("failed to enqueue Analyze request: %v", err)
		}
		logging.Debugf(c, "Converted change details (%v) to Tricium request (%v)", change, req)
	}
	return nil
}

// composeChangesQueryURL composes the URL used to query Gerrit for updated
// changes after the timestamps given in the project poll information, together
// with the given result offset (used to handle paging).
func composeChangesQueryURL(p *GerritProject, offset int) string {
	v := url.Values{}
	v.Add("start", strconv.Itoa(offset))
	v.Add("o", "CURRENT_REVISION")
	v.Add("o", "CURRENT_FILES")
	v.Add("q", fmt.Sprintf("project:%s after:\"%s\"", p.Project,
		p.LastPoll.Format(timeStampLayout)))
	return fmt.Sprintf("%s/a/changes/?%s", p.Instance, v.Encode())
}

// gerritProjectID constructs the ID used to store information about
// a Gerrit instance and project.
func gerritProjectID(instance, project string) string {
	return fmt.Sprintf("%s:%s", instance, project)
}
