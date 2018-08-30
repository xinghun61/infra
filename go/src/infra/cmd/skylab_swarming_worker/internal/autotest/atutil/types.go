// Copyright 2018 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package atutil

// AdminTaskType is an enum used in AdminTask to determine what type
// of admin task to run.
type AdminTaskType int

// Task constants.
const (
	// NoTask can be used as a null AdminTaskType value.
	NoTask AdminTaskType = iota
	Verify
	Cleanup
	Reset
	Repair
)

//go:generate stringer -type=AdminTaskType

// HostInfoSubDir is the filename of the directory for storing host info.
//
// TODO(ayatane): Move this elsewhere.
const HostInfoSubDir = "host_info_store"
