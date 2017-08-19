// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package buildevent

import (
	"time"

	pb "infra/libs/bqschema/tabledef"
)

// CompletedStepLegacyTable defines the BigQuery table to use for
// CompletedStepLegacy schema.
var CompletedStepLegacyTable = pb.TableDef{
	Dataset:                    pb.TableDef_RAW_EVENTS,
	TableId:                    "completed_step_legacy",
	Name:                       "Legacy build events",
	Description:                "Legacy record of build steps.",
	PartitionTable:             true,
	PartitionExpirationSeconds: 0,
}

// CompletedStepLegacy is a BigQuery schema structure that can be used to
// define a completed build step.
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
type CompletedStepLegacy struct {
	Master           string       `bigquery:"master"`
	Builder          string       `bigquery:"builder"`
	BuildNumber      int32        `bigquery:"build_number"`
	BuildSchedMsec   int64        `bigquery:"build_sched_msec"`
	StepName         string       `bigquery:"step_name"`
	StepText         string       `bigquery:"step_text"`
	StepNumber       int32        `bigquery:"step_number"`
	HostName         string       `bigquery:"host_name"`
	Result           LegacyResult `bigquery:"result"`
	StepStartedMsec  int64        `bigquery:"step_started_msec"`
	StepDurationS    float32      `bigquery:"step_duration_s"`
	PatchURL         string       `bigquery:"patch_url"`
	Project          string       `bigquery:"project"`
	BBucketID        string       `bigquery:"bbucket_id"`
	BBucketUserAgent string       `bigquery:"bbucket_user_agent"`

	// The following fields are NOT part of the original BuildBot schema. These
	// are candidate for direct translation into the non-legacy schema, when it
	// is implemented.

	// BuildID is a unique identifier for this build. It can be artibrary, but
	// it will be consistent for all records emitted by this build, so it can be
	// used to correlate those records.
	BuildID string `bigquery:"build_id"`

	StepStarted  time.Time `bigquery:"step_started"`
	StepFinished time.Time `bigquery:"step_started"`
}
