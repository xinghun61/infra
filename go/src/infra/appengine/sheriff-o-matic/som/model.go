// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package som

import (
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/url"
	"strconv"
	"strings"
	"time"

	"github.com/luci/gae/service/datastore"
	"github.com/luci/luci-go/common/clock"
	"github.com/luci/luci-go/common/data/stringset"
	"github.com/luci/luci-go/server/auth"
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

// AlertsJSON is the a JSON blob of alerts for a tree.
type AlertsJSON struct {
	ID       int64          `gae:"$id" json:"-"`
	Tree     *datastore.Key `gae:"$parent"`
	Date     time.Time
	Contents []byte `gae:",noindex"`
}

// Annotation is any information sheriffs want to annotate an alert with. For
// example, a bug where the cause of the alert is being solved.
type Annotation struct {
	KeyDigest        string    `gae:"$id"`
	Key              string    `gae:",noindex" json:"key"`
	Bugs             []string  `gae:",noindex" json:"bugs"`
	Comments         []Comment `gae:",noindex" json:"comments"`
	SnoozeTime       int       `json:"snoozeTime"`
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
}

type annotationRemove struct {
	Time     bool     `json:"snoozeTime"`
	Bugs     []string `json:"bugs"`
	Comments []int    `json:"comments"`
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

// Adds some data to an annotation. Returns true if a refresh of annotation
// metadata (currently monorail data) is required, and any errors encountered.
func (a *Annotation) add(c context.Context, r io.Reader) (bool, error) {
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

	if change.Comments != nil {
		user := auth.CurrentIdentity(c)
		time := clock.Now(c)
		comments := make([]Comment, len(change.Comments))
		for i, c := range change.Comments {
			comments[i].Text = c
			comments[i].User = user.Email()
			comments[i].Time = time
		}

		a.Comments = append(a.Comments, comments...)
		modified = true
	}

	if modified {
		a.ModificationTime = clock.Now(c)
	}

	return needRefresh, nil
}

// Removes some data to an annotation. Returns if a refreshe of annotation
// metadata (currently monorail data) is required, and any errors encountered.
func (a *Annotation) remove(c context.Context, r io.Reader) (bool, error) {
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
	for _, i := range change.Comments {
		if i < 0 || i >= len(a.Comments) {
			return false, errors.New("Invalid comment index")
		}
		a.Comments = append(a.Comments[:i], a.Comments[i+1:]...)
		modified = true
	}

	if modified {
		a.ModificationTime = clock.Now(c)
	}

	return false, nil
}
