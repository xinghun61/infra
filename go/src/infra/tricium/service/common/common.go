// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package common implements common functionality for the Tricium service modules.
package common

import (
	"html/template"
	"net/http"
	"strconv"
	"time"

	"golang.org/x/net/context"

	"google.golang.org/appengine/datastore"
	"google.golang.org/appengine/log"
)

// AnalysisTask includes information needed to start a new analysis task.
// This include the context of a change and details needed for a change in
// that context.
type AnalysisTask struct {
	Context ChangeContext
	// This field should have a value if the context is Gerrit.
	GerritChange GerritChangeDetails
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

// ChangeContext enum
type ChangeContext int

const (
	// GERRIT should be used to indicate that a change is from Gerrit.
	GERRIT ChangeContext = 1 + iota
	// Add new change contexts here.
)

var contexts = [...]string{
	"",
	"GERRIT",
	// Add name of new change context here.
}

// TODO(emso): Panics if ctx is out of bounds. Consider using https://godoc.org/golang.org/x/tools/cmd/stringer instead.
func (ctx ChangeContext) String() string {
	return contexts[ctx]
}

// RunKind enum
type RunKind int

const (
	// TEST should be used for test runs.
	TEST RunKind = 1 + iota
	// LIVE should be used for all non-test requests.
	LIVE
)

var kinds = [...]string{
	"",
	"TEST",
	"LIVE",
}

func (kind RunKind) String() string {
	return kinds[kind]
}

// RunState enum
type RunState int

const (
	// RECEIVED means a run request has been received but not launched.
	RECEIVED RunState = 1 + iota
	// LAUNCHED means the workflow for a request has been launched.
	LAUNCHED
	// DONE means all nodes in the workflow of a request have completed.
	DONE
)

var states = [...]string{
	"",
	"RECEIVED",
	"LAUNCHED",
	"DONE",
}

func (state RunState) String() string {
	return states[state]
}

// Run represents a run of one or more analyses on a change.
type Run struct {
	ID            int64
	Received      time.Time
	RunKind       RunKind
	RunState      RunState
	ChangeContext ChangeContext
	ChangeURL     string
}

// NewRun creates a new run entry with a newly created ID and adds it to
// internal storage for tracking. The created ID is returned.
func NewRun(ctx context.Context, cctx ChangeContext, curl string) (int64, error) {
	// Create ID for run.
	id, err := CreateNextRunID(ctx)
	if err != nil {
		return -1, err
	}
	// Create entry for run and add to datastore.
	key := datastore.NewKey(ctx, "Run", "", id, nil)
	run := &Run{
		ID:       id,
		Received: time.Now(),
		RunKind:  TEST, //  TODO(emso): update this to LIVE
		RunState: RECEIVED,
	}
	if cctx == GERRIT {
		run.ChangeContext = GERRIT
		run.ChangeURL = curl
	}
	return id, StoreRunUpdates(ctx, key, run)
}

// GetRunKey creates a datastore key from a string representation of a run ID.
func GetRunKey(ctx context.Context, si string) (*datastore.Key, error) {
	id, err := strconv.ParseInt(si, 10, 64)
	if err != nil {
		return nil, err
	}
	return datastore.NewKey(ctx, "Run", "", id, nil), nil
}

// GetRun fetches the entry for a run from datastore given a datastore key.
func GetRun(ctx context.Context, key *datastore.Key) (*Run, error) {
	run := new(Run)
	if err := datastore.Get(ctx, key, run); err != nil {
		return nil, err
	}
	return run, nil
}

// StoreRunUpdates stores the given run object. This will overwrite any
// previous run object with the same key.
// TODO(emso): Remove this abstraction around the datastore put call.
func StoreRunUpdates(ctx context.Context, key *datastore.Key, run *Run) error {
	if _, err := datastore.Put(ctx, key, run); err != nil {
		return err
	}
	return nil
}

// ShowResultsPage executes the results page template
func ShowResultsPage(ctx context.Context, w http.ResponseWriter, runs []Run) {
	data := map[string]interface{}{
		"Runs": runs,
	}
	executeTemplate(ctx, template.Must(template.ParseFiles("templates/results.html")), w, data)
}

// ShowBasePage executes the base page template
func ShowBasePage(ctx context.Context, w http.ResponseWriter, d interface{}) {
	executeTemplate(ctx, template.Must(template.ParseFiles("templates/base.html")), w, d)
}

func executeTemplate(ctx context.Context, t *template.Template, w http.ResponseWriter, d interface{}) {
	if err := t.Execute(w, d); err != nil {
		ReportServerError(ctx, w, err)
	}
}

// Counter is used for incrementing of the run ID.
type counter struct {
	Count int64
}

// CreateNextRunID creates the next run ID to use by incrementing
// and internal counter in datastore.
func CreateNextRunID(ctx context.Context) (int64, error) {
	key := datastore.NewKey(ctx, "Counter", "RunCounter", 0, nil)
	counter := new(counter)
	// TODO(emso): Use datastore generated IDs and remove this transaction.
	err := datastore.RunInTransaction(ctx, func(ctx context.Context) error {
		if err := datastore.Get(ctx, key, counter); err != datastore.ErrNoSuchEntity {
			return err
		}
		counter.Count++
		_, err := datastore.Put(ctx, key, counter)
		return err
	}, nil)
	return counter.Count, err
}

// ReportServerError reports back a server error (http code 500).
func ReportServerError(ctx context.Context, w http.ResponseWriter, err error) {
	log.Errorf(ctx, "Error: %v", err)
	http.Error(w, "An internal server error occured. We are working on it ;)",
		http.StatusInternalServerError)
}
