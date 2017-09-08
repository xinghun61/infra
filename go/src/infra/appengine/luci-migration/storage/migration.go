// Copyright 2017 The LUCI Authors.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//      http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

package storage

import (
	"fmt"
	"time"

	"go.chromium.org/gae/service/datastore"
)

// BuilderMigration describes a status of a builder migration at the high level.
// It is stored as a part of Builder entity, so it is available in the Builder
// entity queries.
//
// BuilderMigration answers the questions *whether* the builder is
// WAI/correct/fast enough on LUCI.
// It does not answer *why* it is incorrect/slow.
// For such lower level details, see BuilderMigrationDetails entity.
type BuilderMigration struct {
	AnalysisTime time.Time // when migrated was evaluated
	Status       MigrationStatus
	Correctness  float64 // 1 means correct. <1 means incorrect
	Speed        float64 // 1 means as fast. <1 means slower. >1 means faster.
}

// MigrationStatus describes a status of a builder migration at the highest
// level.
type MigrationStatus int

// Not using iota here because values are persisted in the datastore.
const (
	// StatusUnknown means the status is unknown.
	// This is the initial state when a builder is registered and analysis
	// pipeline did not run yet.
	StatusUnknown MigrationStatus = 0
	// StatusLUCINotWAI means the LUCI builder is incorrect or slow.
	StatusLUCINotWAI MigrationStatus = 1
	// StatusLUCIWAI means the LUCI builder is correct and fast enough.
	StatusLUCIWAI MigrationStatus = 2
	// StatusInsufficientData means there was not enough data to compare
	// Buildbot and LUCI.
	StatusInsufficientData MigrationStatus = 3

	// update String() when adding new values.

	// StatusMigrated means the builder has transitioned to LUCI.
	StatusMigrated MigrationStatus = 100
	// StatusMigrated must be the last one. Do not add new values after this.
)

// String returns a short human-consumable description of the status.
func (s MigrationStatus) String() string {
	switch s {
	case StatusUnknown:
		return "Unknown"

	case StatusLUCINotWAI:
		return "LUCI not WAI"

	case StatusLUCIWAI:
		return "LUCI WAI"

	case StatusInsufficientData:
		return "Not enough data to analyze"

	case StatusMigrated:
		return "Migrated"

	default:
		panic(fmt.Errorf("invalid migration status %d", s))
	}
}

// BuilderMigrationDetails describes a status of a builder migration at the low
// level.
// It is a datastore model.
//
// Entity key. Parent is Builder entity. ID is constant "latest".
type BuilderMigrationDetails struct {
	_id    string         `gae:"$id,latest"`
	Parent *datastore.Key `gae:"$parent"` // Builder entity

	// TrustedHTML is HTML-formatted human-consumable report explaining builder
	// correctness and speed scores, and any additional information useful for
	// drilling down.
	//
	// It is produced by an analysis pipeline.
	// The format and info included in this report is implementation details
	// of the analysis pipeline, thus HTML format.
	TrustedHTML string `gae:",noindex"`
}
