// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package buildevent

import (
	"time"

	pb "infra/libs/bqschema/tabledef"
)

// CompletedBuildLegacyTable defines the BigQuery table to use for
// LegacyCompletedBuild schema.
var CompletedBuildLegacyTable = pb.TableDef{
	Dataset:                    pb.TableDef_RAW_EVENTS,
	TableId:                    "completed_builds_legacy",
	Name:                       "Legacy completed builds",
	Description:                "Record of legacy completed build records.",
	PartitionTable:             true,
	PartitionExpirationSeconds: 0,
}

// CompletedBuildLegacy is a BigQuery schema structure that can be used to
// define a build event.
//
// This is "legacy" because it mirrors the structure of BuildBot events. These
// events do not take advantage of the organizational and metadata capabilities
// that BigQuery offers. A new, non-legacy table is planned which will initially
// coexist with and ultimately deprecate this table.
//
// Fields with either information we cannot access or that are not used in
// current monitoring have been removed.
//
// TODO: Deprecate this in favor of a rich BigQuery schema.
type CompletedBuildLegacy struct {
	Master              string         `bigquery:"master"`
	Builder             string         `bigquery:"builder"`
	BuildNumber         int32          `bigquery:"build_number"`
	BuildSchedMsec      int64          `bigquery:"build_sched_msec"`
	BuildStartedMsec    int64          `bigquery:"build_started_msec"`
	BuildFinishedMsec   int64          `bigquery:"build_finished_msec"`
	HostName            string         `bigquery:"host_name"`
	Result              LegacyResult   `bigquery:"result"`
	QueueDurationS      float32        `bigquery:"queue_duration_s"`
	ExecutionDurationS  float32        `bigquery:"execution_duration_s"`
	TotalDurationS      float32        `bigquery:"total_duration_s"`
	PatchURL            string         `bigquery:"patch_url"`
	Category            LegacyCategory `bigquery:"category"`
	BBucketID           string         `bigquery:"bbucket_id"`
	BBucketUserAgent    string         `bigquery:"bbucket_user_agent"`
	HeadRevisionGitHash string         `bigquery:"head_revision_git_hash"`

	// The following fields are NOT part of the original BuildBot schema. These
	// are candidates for direct translation into the non-legacy schema, when it
	// is implemented.

	// BuildID is a unique identifier for this build. It can be artibrary, but
	// it will be consistent for all records emitted by this build, so it can be
	// used to correlate those records.
	BuildID string `bigquery:"build_id"`

	BBucket string `bigquery:"bbucket_bucket"`

	BuildScheduled time.Time `bigquery:"build_scheduled"`
	BuildStarted   time.Time `bigquery:"build_started"`
	BuildFinished  time.Time `bigquery:"build_finished"`

	Swarming *SwarmingInfo `bigquery:"swarming"`
	Kitchen  *KitchenInfo  `bigquery:"kitchen"`
	Recipes  *RecipeInfo   `bigquery:"recipes"`
}

// KitchenInfo represents information about a Kitchen execution.
type KitchenInfo struct {
	Version string `bigquery:"version"`
}

// SwarmingInfo represents information about a Swarming execution.
type SwarmingInfo struct {
	Host  string `bigquery:"host"`
	RunID string `bigquery:"run_id"`
}

// RecipeInfo represents information about a recipe engine execution and its
// environment.
type RecipeInfo struct {
	Repository string `bigquery:"repository"`
	Revision   string `bigquery:"revision"`
	Name       string `bigquery:"name"`
}

type LegacyResult string

const (
	UNKNOWN       LegacyResult = ""
	SUCCESS                    = "SUCCESS"
	FAILURE                    = "FAILURE"
	INFRA_FAILURE              = "INFRA_FAILURE"
	WARNING                    = "WARNING"
	SKIPPED                    = "SKIPPED"
	RETRY                      = "RETRY"
)

type LegacyCategory string

const (
	CATEGORY_UNKNOWN         LegacyCategory = ""
	CATEGORY_CQ                             = "CQ"
	CATEGORY_CQ_EXPERIMENTAL                = "CQ_EXPERIMENTAL"
	CATEGORY_GIT_CL_TRY                     = "GIT_CL_TRY"
)
