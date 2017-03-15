// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package admin

import (
	"fmt"

	"infra/tricium/api/v1"
)

// GetNext returns the names of successing workers of the given worker.
func (wf *Workflow) GetNext(cw string) []string {
	for _, w := range wf.Workers {
		if w.Name == cw {
			return w.Next
		}
	}
	return nil
}

// RootWorkers returns the list of root worker names.
//
// Root workers are those workers in need of the initial Tricium
// data type, i.e., Git file details.
func (wf *Workflow) RootWorkers() []string {
	var rw []string
	for _, w := range wf.Workers {
		if w.Needs == tricium.Data_GIT_FILE_DETAILS {
			rw = append(rw, w.Name)
		}
	}
	return rw
}

// GetWorker returns the worker matching the given name.
//
// An unknown worker results in an error.
func (wf *Workflow) GetWorker(name string) (*Worker, error) {
	for _, w := range wf.Workers {
		if w.Name == name {
			return w, nil
		}
	}
	return nil, fmt.Errorf("unknown worker: %s", name)
}
