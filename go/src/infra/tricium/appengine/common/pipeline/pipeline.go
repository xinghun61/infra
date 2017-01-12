// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package pipeline implements shared pipeline functionality for the Tricium service modules.
package pipeline

import (
	"fmt"
	"net/url"
	"strconv"
)

// ServiceRequest lists information needed to make an analysis request to the service.
//
// This struct lists the expected fields of an entry in the service queue.
type ServiceRequest struct {
	// The name of the project connected to Tricium.
	Project string `url:"project"`
	// The Git ref to use in the Git repo connected to the project.
	GitRef string `url:"git-ref"`
	// Paths to files to analyze (from the repo root).
	Paths []string `url:"path"`
}

// ParseServiceRequest creates and populates a ServiceRequest struct from URL values.
//
// An error is raised if one or more values are missing.
func ParseServiceRequest(v url.Values) (*ServiceRequest, error) {
	res := &ServiceRequest{
		Project: v.Get("project"),
		GitRef:  v.Get("git-ref"),
	}
	if p := v["path"]; len(p) != 0 {
		res.Paths = make([]string, len(p))
		copy(res.Paths, p)
	}
	if res.Project == "" || res.GitRef == "" || len(res.Paths) == 0 {
		return nil, fmt.Errorf("failed to parse service request, missing values: %#v", res)
	}
	return res, nil
}

// LaunchRequest lists information needed to launch a workflow for a run.
//
// A run correspond to one instance of a request.
type LaunchRequest struct {
	RunID int64 `url:"run-id"`
	// The name of the project connected to Tricium.
	Project string `url:"project"`
	// The Git ref to use in the Git repo connected to the project.
	GitRef string `url:"git-ref"`
	// Paths to files to analyze (from the repo root).
	Paths []string `url:"path"`
	// URL to the Git repo connected to this project.
	GitRepo string `url:"git-repo"`
}

// ParseLaunchRequest creates and populates a LaunchRequest struct from URL values.
// An error is raised if one or more values are missing.
func ParseLaunchRequest(v url.Values) (*LaunchRequest, error) {
	fmt.Printf("Converting URL values to launch request: %v", v)
	res := &LaunchRequest{
		Project: v.Get("project"),
		GitRepo: v.Get("git-repo"),
		GitRef:  v.Get("git-ref"),
	}
	runID := v.Get("run-id")
	if p := v["path"]; len(p) != 0 {
		res.Paths = make([]string, len(p))
		copy(res.Paths, p)
	}
	if runID == "" || res.Project == "" || res.GitRepo == "" ||
		res.GitRef == "" || len(res.Paths) == 0 {
		return nil, fmt.Errorf("failed to parse launch request, missing values (id: %s)", runID)
	}
	r, err := strconv.Atoi(runID)
	if err != nil {
		return nil, fmt.Errorf("failed to parse launcher request, failed to convert run ID (id: %s)", runID)
	}
	res.RunID = int64(r)
	return res, nil
}

// DriverRequest lists information needed to launch a worker and drive the workflow from that worker.
type DriverRequest struct {
	Kind  DriverRequestKind `url:"kind"`
	RunID int64             `url:"run-id"`
	// The hash to the isolated input with Tricium data needed by this worker.
	IsolatedInput string `url:"isolated-input"`
	// The name of the worker to launch a swarming task for.
	Worker string `url:"worker"`
}

// DriverRequestKind specifies the kind of driver request, trigger or collect.
type DriverRequestKind uint8

const (
	// DriverTrigger is for driver requests that should trigger a swarming task for a worker.
	DriverTrigger DriverRequestKind = iota + 1
	// DriverCollect is for driver requests that should collect results for a worker.
	DriverCollect
)

// ParseDriverRequest creates and populates a DriverRequest struct from URL values.
// An error is raised if one or more values are missing.
func ParseDriverRequest(v url.Values) (*DriverRequest, error) {
	res := &DriverRequest{
		IsolatedInput: v.Get("isolated-input"),
		Worker:        v.Get("worker"),
	}
	kind := v.Get("kind")
	runID := v.Get("run-id")
	if kind == "" || runID == "" || res.IsolatedInput == "" || res.Worker == "" {
		return nil, fmt.Errorf("failed to parse driver request, missing values (id: %s)", runID)
	}
	r, err := strconv.Atoi(runID)
	if err != nil {
		return nil, fmt.Errorf("failed to parse driver request, failed to convert run ID (id: %s)", runID)
	}
	res.RunID = int64(r)
	k, err := strconv.Atoi(kind)
	if err != nil {
		return nil, fmt.Errorf("failed to parse driver request, failed to convert request kind (id: %s)", runID)
	}
	res.Kind = DriverRequestKind(k)
	return res, nil
}

// TrackRequest lists information needed to report progress for a request, workflow, or worker.
type TrackRequest struct {
	Kind  TrackRequestKind `url:"kind"`
	RunID int64            `url:"run-id"`
	// The hash to the isolated input with Tricium data needed by the named worker.
	// Included in 'worker-launched'.
	IsolatedInput string `url:"isolated-input,omitempty"`
	// The name of the worker.
	// Included in 'worker-launched' and 'worker-done'.
	Worker string `url:"worker,omitempty"`
	// URL to the swarming server.
	// Included in 'worker-launched'.
	SwarmingURL string `url:"swarming-url,omitempty"`
	// Swarming task ID.
	// Included in 'worker-launched'.
	TaskID string `url:"task-id,omitempty"`
	// The hash to the isolated output, with Tricium data, provided by the named worker.
	// Included in 'worker-done'.
	IsolatedOutput string `url:"isolated-output,omitempty"`
	// Included in 'worker-done'.
	ExitCode int `url:"exit-code"`
}

// TrackRequestKind specifies the kind of reporter request.
type TrackRequestKind uint8

const (
	// TrackWorkflowLaunched is for when a workflow has been launched by the launcher.
	TrackWorkflowLaunched TrackRequestKind = iota + 1
	// TrackWorkerLaunched is for when a worker has been launched by the driver.
	TrackWorkerLaunched
	// TrackWorkerDone is for when a worker is done and results have been collected.
	TrackWorkerDone
)

// ParseTrackRequest creates and populates a TrackRequest struct from URL values.
// An error is raised if one or more values are missing. Required values vary depending on
// request kind.
func ParseTrackRequest(v url.Values) (*TrackRequest, error) {
	kind := v.Get("kind")
	runID := v.Get("run-id")
	if kind == "" || runID == "" {
		return nil, fmt.Errorf("failed to parse reporter request, missing values (id: %s)", runID)
	}
	r, err := strconv.ParseInt(runID, 10, 64)
	if err != nil {
		return nil, fmt.Errorf("failed to parse reporter request, failed to convert run ID (id: %s): %v", runID, err)
	}
	res := &TrackRequest{
		RunID: r,
	}
	k, err := strconv.Atoi(kind)
	if err != nil {
		return nil, fmt.Errorf("failed to parse reporter request, failed to convert request kind (id: %s): %v", runID, err)
	}
	res.Kind = TrackRequestKind(k)
	switch res.Kind {
	case TrackWorkflowLaunched:
		// Nothing more to check for this kind.
	case TrackWorkerLaunched:
		res.Worker = v.Get("worker")
		res.IsolatedInput = v.Get("isolated-input")
		res.SwarmingURL = v.Get("swarming-url")
		res.TaskID = v.Get("task-id")
		if res.Worker == "" || res.IsolatedInput == "" || res.SwarmingURL == "" || res.TaskID == "" {
			return nil, fmt.Errorf("failed to parse track request, missing values for kind worker-launched (id: %s)", runID)
		}
	case TrackWorkerDone:
		res.Worker = v.Get("worker")
		res.IsolatedOutput = v.Get("isolated-output")
		exitCode := v.Get("exit-code")
		if res.Worker == "" || res.IsolatedOutput == "" || exitCode == "" {
			return nil, fmt.Errorf("failed to parse track request, missing values for kind worker-done (id: %s)", runID)
		}
		res.ExitCode, err = strconv.Atoi(exitCode)
		if err != nil {
			return nil, fmt.Errorf("failed to parse track request, failed to convert exit code (id: %s): %v", runID, err)
		}
	default:
		return nil, fmt.Errorf("unknown track request kind: %d", res.Kind)
	}
	return res, nil
}
