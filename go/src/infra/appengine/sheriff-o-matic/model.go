// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package som

import (
	"encoding/json"
	"fmt"
	"io"
	"net/url"
	"strconv"
	"strings"
	"time"

	"github.com/luci/gae/service/datastore"
	"github.com/luci/luci-go/common/clock"
	"github.com/luci/luci-go/common/data/stringset"
	"golang.org/x/net/context"
)

// Tree is a tree which sheriff-o-matic receives and groups alerts for.
type Tree struct {
	Name          string   `gae:"$id" json:"name"`
	DisplayName   string   `json:"display_name"`
	AlertStreams  []string `json:"alert_streams,omitempty"`
	BugQueueLabel string   `json:"bug_queue_label,omitempty"`
	HelpLink      string   `json:"help_link,omitempty"`
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
	KeyDigest        string   `gae:"$id"`
	Key              string   `gae:",noindex" json:"key"`
	Bugs             []string `gae:",noindex" json:"bugs"`
	SnoozeTime       int      `json:"snoozeTime"`
	ModificationTime time.Time
}

type annotationAdd struct {
	Time int      `json:"snoozeTime"`
	Bugs []string `json:"bugs"`
}

type annotationRemove struct {
	Time bool     `json:"snoozeTime"`
	Bugs []string `json:"bugs"`
}

func validBug(bug string) (string, error) {
	asInt, err := strconv.Atoi(bug)
	if err == nil {
		return fmt.Sprintf("https://crbug.com/%d", asInt), nil
	}

	urlBug := bug
	if !strings.HasPrefix(bug, "https://") {
		urlBug = "https://" + urlBug
	}

	parsed, err := url.Parse(urlBug)
	if err == nil {
		if strings.Contains(parsed.Host, "bugs.chromium.org") ||
			strings.Contains(parsed.Host, "crbug.com") {
			return urlBug, nil
		}
	}

	return "", fmt.Errorf("Invalid bug '%s'", bug)
}

func (a *Annotation) add(c context.Context, r io.Reader) error {
	change := &annotationAdd{}

	err := json.NewDecoder(r).Decode(change)
	if err != nil {
		return err
	}

	for i, bug := range change.Bugs {
		newBug, err := validBug(bug)
		if err != nil {
			return err
		}
		change.Bugs[i] = newBug
	}

	modified := false

	if change.Time != 0 {
		a.SnoozeTime = change.Time
		modified = true
	}

	if change.Bugs != nil {
		a.Bugs = stringset.NewFromSlice(
			append(a.Bugs, change.Bugs...)...).ToSlice()
		modified = true
	}

	if modified {
		a.ModificationTime = clock.Now(c)
	}

	return nil
}

func (a *Annotation) remove(c context.Context, r io.Reader) error {
	change := &annotationRemove{}

	err := json.NewDecoder(r).Decode(change)
	if err != nil {
		return err
	}

	for i, bug := range change.Bugs {
		newBug, err := validBug(bug)
		if err != nil {
			return err
		}
		change.Bugs[i] = newBug
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

	if modified {
		a.ModificationTime = clock.Now(c)
	}

	return nil
}
