// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package frontend

import (
	"fmt"
)

// GerritChangeToRunID maps a Gerrit change ID to a run ID.
//
// Each change ID is mapped to the latest run ID for that change ID.
// This should typically correspond to the latest patch set for the change.
//
// Mutable entity.
// LUCI datastore ID (=string on the form project:changeID) field.
type GerritChangeToRunID struct {
	ID    string `gae:"$id"`
	RunID int64
}

func gerritMappingID(host, project, changeID string) string {
	return fmt.Sprintf("%s##%s##%s", host, project, changeID)
}
