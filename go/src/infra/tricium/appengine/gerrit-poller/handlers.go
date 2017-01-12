// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package gerritpoller implements HTTP handlers for the gerrit-poller module.
package gerritpoller

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"io/ioutil"
	"net/http"
	"net/url"
	"sort"
	"strconv"
	"time"

	"github.com/google/go-querystring/query"
	"github.com/luci/luci-go/server/router"

	"golang.org/x/build/gerrit"
	"golang.org/x/net/context"
	"golang.org/x/oauth2"
	"golang.org/x/oauth2/google"

	"google.golang.org/appengine"
	"google.golang.org/appengine/datastore"
	"google.golang.org/appengine/log"
	"google.golang.org/appengine/taskqueue"
	"google.golang.org/appengine/urlfetch"

	"infra/tricium/appengine/common"
	"infra/tricium/appengine/common/pipeline"
)

const (
	instance = "https://chromium-review.googlesource.com"
	scope    = "https://www.googleapis.com/auth/gerritcodereview"
	project  = "playground/gerrit-tricium"
)

// The timestamp format used by Gerrit (using the reference date). All timestamps are in UTC.
const timeStampLayout = "2006-01-02 15:04:05.000000000"

// GerritProject represents the pollers view of a Gerrit project.
// This includes data about the last poll; timestamp and last seen change ID of the previous poll.
// Timestamp of last successful poll.
// Datastore key used: instance:project
type GerritProject struct {
	ID       string `datastore:"-"`
	Instance string `datastore:"-"`
	Project  string `datastore:"-"`
	LastPoll time.Time
}

// GerritChange represents the last seen revision for a change in Gerrit and is stored
// as a child of GerritProject.
// Datastore key used: changeID
type GerritChange struct {
	ChangeID     string
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

func init() {
	r := router.New()
	base := common.MiddlewareForInternal()

	r.GET("/gerrit-poller/internal/poll", base, pollHandler)

	http.DefaultServeMux.Handle("/", r)
}

// pollHandler queries Gerrit for changes since the last poll.
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
func pollHandler(c *router.Context) {
	ctx := common.NewGAEContext(c)

	// TODO(emso): Get project/instance from luci-config

	// Get last poll data for the given instance/project.
	p, err := readProjectData(ctx, instance, project)
	if err != nil {
		common.ReportServerError(c, err)
		return
	}
	// If no previous poll, store current time and return.
	if p.LastPoll.IsZero() {
		log.Infof(ctx, "No previous poll for %s/%s. Storing current timestamp and stopping.",
			instance, project)
		p.ID = gerritProjectID(instance, project)
		p.Instance = instance
		p.Project = project
		p.LastPoll = time.Now()
		if err := storeProjectData(ctx, p); err != nil {
			common.ReportServerError(c, err)
		}
		return
	}
	log.Infof(ctx, "Last poll: %+v", p)

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
		chgs, more, err := queryChanges(ctx, p, s)
		if err != nil {
			common.ReportServerError(c, err)
			return
		}
		s += len(chgs)
		changes = append(changes, chgs...)
		// Check if we need to query for more changes, that is, if the
		// results were truncated.
		if !more {
			break
		}
	}

	if len(changes) == 0 {
		// No changes found.
		log.Infof(ctx, "Poll done. No changes found.")
		return
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
	if err := datastore.RunInTransaction(ctx, func(ctx context.Context) error {
		// Update tracking of changes, getting back updated changes.
		uc, err := updateTracking(ctx, p, changes)
		if err != nil {
			return err
		}
		// Update tracking of last poll.
		p.LastPoll = changes[0].Updated.Time()
		if err := storeProjectData(ctx, p); err != nil {
			return err
		}
		// Convert to analysis tasks and enqueue.
		changeDetails := convertToChangeDetails(p, uc)
		return enqueueServiceRequests(ctx, changeDetails)
	}, nil); err != nil {
		common.ReportServerError(c, err)
		return
	}
	log.Infof(ctx, "Poll done. Processed %d change(s).", len(changes))
}

// updateTracking updates the tracking of the given Gerrit project based on the list of
// updated changes. Returns a list of changes where the tracked revision and the current
// revision differ.
func updateTracking(ctx context.Context, p *GerritProject, changes []gerrit.ChangeInfo) ([]gerrit.ChangeInfo, error) {
	var diff []gerrit.ChangeInfo
	// Create list of datastore keys.
	pkey := datastore.NewKey(ctx, "GerritProject", p.ID, 0, nil)
	keys := make([]*datastore.Key, len(changes))
	for i, change := range changes {
		keys[i] = datastore.NewKey(ctx, "GerritChange", change.ChangeID, 0, pkey)
	}
	// Get list of tracked changes.
	tc := make([]*GerritChange, len(keys))
	if err := datastore.GetMulti(ctx, keys, tc); err != nil {
		if me, ok := err.(appengine.MultiError); ok {
			for _, merr := range me {
				if merr != nil && merr != datastore.ErrNoSuchEntity {
					return diff, err
				}
			}
		} else {
			log.Infof(ctx, "Getting tracked changes failed: %v", err)
			return diff, err
		}
	}
	// TODO(emso): consider depending on the order provided by datastore, that is, depend
	// on keys and values being in the same order from GetMulti.
	// Create map of tracked changes.
	t := make(map[string]GerritChange)
	for _, c := range tc {
		if c != nil {
			t[c.ChangeID] = *c
		}
	}
	log.Infof(ctx, "Found the following tracked changes: %v", t)
	// Compare polled changes to tracked changes, update tracking and add to the
	// diff list when there is an updated revision change.
	var uchanges []*GerritChange
	var ukeys []*datastore.Key
	var dkeys []*datastore.Key
	for _, change := range changes {
		c, ok := t[change.ChangeID]
		key := datastore.NewKey(ctx, "GerritChange", change.ChangeID, 0, pkey)
		switch {
		// For untracked and new/draft, start tracking.
		case !ok && (change.Status == "NEW" || change.Status == "DRAFT"):
			log.Infof(ctx, "Found untracked %s change (%s); tracking.", change.Status, change.ChangeID)
			c.ChangeID = change.ChangeID
			c.LastRevision = change.CurrentRevision
			// The ukeys and uchanges slices must be mutated together.
			ukeys = append(ukeys, key)
			uchanges = append(uchanges, &c)
			diff = append(diff, change)
		// Untracked and not new/draft, move on to the next change.
		case !ok:
			log.Infof(ctx, "Found untracked %s change (%s); leaving untracked.", change.Status, change.ChangeID)
		// For tracked and merged/abandoned, stop tracking (clean up).
		case change.Status == "MERGED" || change.Status == "ABANDONED":
			log.Infof(ctx, "Found tracked %s change (%s); removing.",
				change.Status, change.ChangeID)
			// Note that we are only adding keys for entries already present in the
			// datastore to the delete list. That is, we should not get any NoSuchEntity
			// errors.
			dkeys = append(dkeys, key)
		// For tracked and unseen revision, update tracking and to diff list.
		case c.LastRevision != change.CurrentRevision:
			log.Infof(ctx, "Found tracked %s change (%s) with new revision; updating.", change.Status, change.ChangeID)
			c.LastRevision = change.CurrentRevision
			// The ukeys and uchanges slices must be mutated together.
			ukeys = append(ukeys, key)
			uchanges = append(uchanges, &c)
			diff = append(diff, change)
		default:
			log.Infof(ctx, "Found tracked %s change (%s) with no update; leaving as is.", change.Status, change.ChangeID)
		}
	}
	// Update stored data.
	if _, err := datastore.PutMulti(ctx, ukeys, uchanges); err != nil {
		return diff, err
	}
	if err := datastore.DeleteMulti(ctx, dkeys); err != nil {
		if me, ok := err.(appengine.MultiError); ok {
			for _, merr := range me {
				if merr != datastore.ErrNoSuchEntity {
					// Some error other than entity not found, report.
					return diff, err
				}
			}
		} else {
			return diff, err
		}
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
func queryChanges(ctx context.Context, p *GerritProject, offset int) ([]gerrit.ChangeInfo, bool, error) {
	var changes []gerrit.ChangeInfo
	// Compose, connect and send.
	url := composeChangesQueryURL(p, offset)
	log.Infof(ctx, "Using URL: %s", url)
	req, err := http.NewRequest("GET", url, nil)
	if err != nil {
		return changes, false, err
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Accept", "application/json")
	c := &http.Client{
		Transport: &oauth2.Transport{
			Source: google.AppEngineTokenSource(ctx, scope),
			Base:   &urlfetch.Transport{Context: ctx},
		},
	}
	resp, err := c.Do(req)
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
func enqueueServiceRequests(ctx context.Context, changes []*GerritChangeDetails) error {
	for _, c := range changes {
		// Add to the service queue.
		sr := pipeline.ServiceRequest{
			Project: c.Project,
			GitRef:  c.GitRef,
		}
		var files []string
		for _, file := range c.FileChanges {
			if file.Status != "Delete" {
				files = append(files, file.Path)
			}
		}
		sr.Paths = files
		v, err := query.Values(sr)
		if err != nil {
			return errors.New("failed to encode service request")
		}
		t := taskqueue.NewPOSTTask("internal/queue", v)
		if _, err := taskqueue.Add(ctx, t, common.ServiceQueue); err != nil {
			return err
		}
		log.Infof(ctx, "Converted change details (%v) to service request (%v)", c, sr)
	}
	return nil
}

// readProjectData reads stored data for a given Gerrit instance and project.
func readProjectData(ctx context.Context, instance, project string) (*GerritProject, error) {
	id := gerritProjectID(instance, project)
	key := datastore.NewKey(ctx, "GerritProject", id, 0, nil)
	e := new(GerritProject)
	err := datastore.Get(ctx, key, e)
	if err == datastore.ErrNoSuchEntity {
		log.Infof(ctx, "Found no previous entry for id:%s", id)
		err = nil
	}
	e.ID = id
	e.Instance = instance
	e.Project = project
	return e, err
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
	return fmt.Sprintf("%s/changes/?%s", p.Instance, v.Encode())
}

// storeProjectData stores data for the given Gerrit instance and project.
func storeProjectData(ctx context.Context, p *GerritProject) error {
	log.Infof(ctx, "Storing project data: %+v", p)
	key := datastore.NewKey(ctx, "GerritProject", p.ID, 0, nil)
	_, err := datastore.Put(ctx, key, p)
	return err
}

// gerritProjectID constructs the ID used to store information about
// a Gerrit instance and project.
func gerritProjectID(instance, project string) string {
	return fmt.Sprintf("%s:%s", instance, project)
}
