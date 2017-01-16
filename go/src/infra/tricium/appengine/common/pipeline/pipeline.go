// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package pipeline implements shared pipeline functionality for the Tricium service modules.
package pipeline

import (
	"fmt"
	"net/url"
)

// TODO(emso): Remove this package once the UI calls Tricium.Analyze directly.

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
