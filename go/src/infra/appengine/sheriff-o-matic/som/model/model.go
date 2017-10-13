// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package model

import (
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/url"
	"strconv"
	"strings"
	"time"

	"infra/libs/eventupload"

	"cloud.google.com/go/bigquery"
	"google.golang.org/appengine"

	"go.chromium.org/gae/service/datastore"
	"go.chromium.org/gae/service/info"
	"go.chromium.org/luci/common/clock"
	"go.chromium.org/luci/common/data/stringset"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/server/auth"
	"golang.org/x/net/context"
)

// Tree is a tree which sheriff-o-matic receives and groups alerts for.
type Tree struct {
	Name           string   `gae:"$id" json:"name"`
	DisplayName    string   `json:"display_name"`
	AlertStreams   []string `json:"alert_streams,omitempty"`
	BugQueueLabel  string   `json:"bug_queue_label,omitempty"`
	HelpLink       string   `json:"help_link,omitempty"`
	GerritProject  string   `json:"gerrit_project,omitempty"`
	GerritInstance string   `json:"gerrit_instance,omitempty"`
}

// AlertsJSON is the JSON blob of alerts for a tree.
type AlertsJSON struct {
	ID       int64          `gae:"$id" json:"-"`
	Tree     *datastore.Key `gae:"$parent"`
	Date     time.Time
	Contents []byte `gae:",noindex"`
}

// AlertJSON is the JSON blob of an alert for a tree.
type AlertJSON struct {
	ID           string         `gae:"$id" json:"-"`
	Tree         *datastore.Key `gae:"$parent"`
	Date         time.Time
	Contents     []byte `gae:",noindex"`
	Resolved     bool
	AutoResolved bool
	ResolvedDate time.Time
}

// RevisionSummaryJSON is the JSON blob of a RevisionSummary for a tree.
type RevisionSummaryJSON struct {
	ID       string         `gae:"$id" json:"-"`
	Tree     *datastore.Key `gae:"$parent"`
	Date     time.Time
	Contents []byte `gae:",noindex"`
}

// ResolveRequest is the format of the request to resolve alerts.
type ResolveRequest struct {
	Keys     []string `json:"keys"`
	Resolved bool     `json:"resolved"`
}

// ResolveResponse is the format of the response to resolve alerts.
type ResolveResponse struct {
	Tree     string   `json:"tree"`
	Keys     []string `json:"keys"`
	Resolved bool     `json:"resolved"`
}

// Annotation is any information sheriffs want to annotate an alert with. For
// example, a bug where the cause of the alert is being solved.
type Annotation struct {
	KeyDigest        string    `gae:"$id"`
	Key              string    `gae:",noindex" json:"key"`
	Bugs             []string  `gae:",noindex" json:"bugs"`
	Comments         []Comment `gae:",noindex" json:"comments"`
	SnoozeTime       int       `json:"snoozeTime"`
	GroupID          string    `gae:",noindex" json:"group_id"`
	ModificationTime time.Time
}

// Comment is the format for the data in the Comments property of an Annotation
type Comment struct {
	Text string    `json:"text"`
	User string    `json:"user"`
	Time time.Time `json:"time"`
}

type annotationAdd struct {
	Time     int      `json:"snoozeTime"`
	Bugs     []string `json:"bugs"`
	Comments []string `json:"comments"`
	GroupID  string   `json:"group_id"`
}

type annotationRemove struct {
	Time     bool     `json:"snoozeTime"`
	Bugs     []string `json:"bugs"`
	Comments []int    `json:"comments"`
	GroupID  bool     `json:"group_id"`
}

// Extracts the bug id from a URL or returns the input if the user entered a
// number.
func validBug(bug string) (string, error) {
	urlBug := bug
	if !strings.HasPrefix(bug, "https://") {
		urlBug = "https://" + urlBug
	}

	parsed, err := url.Parse(urlBug)
	if err == nil {
		// Example: bugs.chromium.org?id=123
		if strings.Contains(parsed.Host, "bugs.chromium.org") {
			params, err := url.ParseQuery(parsed.RawQuery)
			if err == nil {
				if id, ok := params["id"]; ok {
					bug = id[0]
				}
			}
		}
		// Example: crbug.com/123
		if strings.Contains(parsed.Host, "crbug.com") {
			bug = strings.Replace(parsed.Path, "/", "", -1)
		}
	}

	_, err = strconv.Atoi(bug)
	if err == nil {
		return bug, nil
	}

	return "", fmt.Errorf("Invalid bug '%s'", bug)
}

// Add adds some data to an annotation. Returns true if a refresh of annotation
// metadata (currently monorail data) is required, and any errors encountered.
func (a *Annotation) Add(c context.Context, r io.Reader) (bool, error) {
	change := &annotationAdd{}
	needRefresh := false

	err := json.NewDecoder(r).Decode(change)
	if err != nil {
		return needRefresh, err
	}

	for i, bug := range change.Bugs {
		newBug, err := validBug(bug)
		if err != nil {
			return needRefresh, err
		}
		change.Bugs[i] = newBug
	}

	modified := false

	if change.Time != 0 {
		a.SnoozeTime = change.Time
		modified = true
	}

	if change.Bugs != nil {
		oldBugs := stringset.NewFromSlice(a.Bugs...)
		newBugs := stringset.NewFromSlice(append(a.Bugs, change.Bugs...)...)
		if newBugs.Difference(oldBugs).Len() != 0 {
			a.Bugs = newBugs.ToSlice()
			needRefresh = true
			modified = true
		}
	}

	user := auth.CurrentIdentity(c)
	commentTime := clock.Now(c)
	if change.Comments != nil {
		comments := make([]Comment, len(change.Comments))
		for i, c := range change.Comments {
			comments[i].Text = c
			comments[i].User = user.Email()
			comments[i].Time = commentTime
		}

		a.Comments = append(a.Comments, comments...)
		modified = true
	}

	if change.GroupID != "" {
		a.GroupID = change.GroupID
		modified = true
	}

	if modified {
		a.ModificationTime = clock.Now(c)
	}

	evt := createAnnotationEvent(c, a, "add")
	evt.Bugs = change.Bugs
	evt.SnoozeTime = time.Unix(int64(a.SnoozeTime/1000), 0)
	evt.GroupId = change.GroupID
	for _, c := range change.Comments {
		evt.Comments = append(evt.Comments, &SOMAnnotationEvent_Comments{
			Text: c,
			User: user.Email(),
			Time: commentTime,
		})
	}

	if err := writeAnnotationEvent(c, evt); err != nil {
		logging.Errorf(c, "error writing annotation event to bigquery: %v", err)
		// Continue. This isn't fatal.
	}

	return needRefresh, nil
}

// Remove removes some data to an annotation. Returns if a refreshe of annotation
// metadata (currently monorail data) is required, and any errors encountered.
func (a *Annotation) Remove(c context.Context, r io.Reader) (bool, error) {
	change := &annotationRemove{}

	err := json.NewDecoder(r).Decode(change)
	if err != nil {
		return false, err
	}

	modified := false

	if change.Time {
		a.SnoozeTime = 0
		modified = true
	}

	if change.Bugs != nil {
		set := stringset.NewFromSlice(a.Bugs...)
		for _, bug := range change.Bugs {
			set.Del(bug)
		}
		a.Bugs = set.ToSlice()
		modified = true
	}

	// Client passes in a list of comment indices to delete.
	deletedComments := []Comment{}
	for _, i := range change.Comments {
		if i < 0 || i >= len(a.Comments) {
			return false, errors.New("Invalid comment index")
		}
		deletedComments = append(deletedComments, a.Comments[i])
		a.Comments = append(a.Comments[:i], a.Comments[i+1:]...)
		modified = true
	}

	if change.GroupID {
		a.GroupID = ""
		modified = true
	}

	if modified {
		a.ModificationTime = clock.Now(c)
	}

	evt := createAnnotationEvent(c, a, "remove")
	evt.Bugs = change.Bugs
	evt.SnoozeTime = time.Unix(int64(a.SnoozeTime), 0)
	evt.GroupId = a.GroupID
	for _, c := range deletedComments {
		evt.Comments = append(evt.Comments, &SOMAnnotationEvent_Comments{
			Text: c.Text,
			User: c.User,
			Time: c.Time,
		})
	}

	if err := writeAnnotationEvent(c, evt); err != nil {
		logging.Errorf(c, "error writing annotation event to bigquery: %v", err)
		// Continue. This isn't fatal.
	}

	return false, nil
}

func createAnnotationEvent(ctx context.Context, a *Annotation, operation string) *SOMAnnotationEvent {
	evt := &SOMAnnotationEvent{
		Timestamp:        a.ModificationTime,
		AlertKeyDigest:   a.KeyDigest,
		AlertKey:         a.Key,
		RequestId:        appengine.RequestID(ctx),
		Operation:        operation,
		ModificationTime: a.ModificationTime,
	}

	for _, c := range a.Comments {
		evt.Comments = append(evt.Comments, &SOMAnnotationEvent_Comments{
			Text: c.Text,
			User: c.User,
			Time: c.Time,
		})
	}

	return evt
}

func writeAnnotationEvent(c context.Context, evt *SOMAnnotationEvent) error {
	client, err := bigquery.NewClient(c, info.AppID(c))
	if err != nil {
		return err
	}
	up := eventupload.NewUploader(c, client, SOMAnnotationEventTable)
	up.SkipInvalidRows = true
	up.IgnoreUnknownValues = true

	return up.Put(c, evt)
}
