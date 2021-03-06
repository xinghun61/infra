// THIS FILE IS AUTOGENERATED. DO NOT MODIFY.

package buildevent

import pb "infra/libs/bqschema/tabledef"
import time "time"

// CompletedStepLegacyTable is the TableDef for the
// "raw_events" dataset's "completed_step_legacy" table.
var CompletedStepLegacyTable = &pb.TableDef{
	DatasetId: "raw_events",
	TableId:   "completed_step_legacy",
}

// CompletedStepLegacy is the schema for "CompletedStepLegacyTable".
type CompletedStepLegacy struct {
	// The name of the BuildBot master.
	Master string `bigquery:"master"`

	// The name of the BuildBot builder.
	Builder string `bigquery:"builder"`

	// The BuildBot build number.
	BuildNumber int64 `bigquery:"build_number"`

	// The build schedule time, in milliseconds from epoch.
	BuildSchedMsec int64 `bigquery:"build_sched_msec"`

	// The name of this step.
	StepName string `bigquery:"step_name"`

	// Step text output.
	StepText string `bigquery:"step_text"`

	// The ordinal of this step, relative to other steps in the build.
	StepNumber int64 `bigquery:"step_number"`

	// The builder host name.
	HostName string `bigquery:"host_name"`

	// The step result (enum).
	Result string `bigquery:"result"`

	// The step's started time, in milliseconds from epoch.
	StepStartedMsec int64 `bigquery:"step_started_msec"`

	// The step's duration, in seconds.
	StepDurationS float64 `bigquery:"step_duration_s"`

	// The patch URL.
	PatchUrl string `bigquery:"patch_url"`

	// The build's project.
	Project string `bigquery:"project"`

	// The BuildBucket ID.
	BbucketId string `bigquery:"bbucket_id"`

	// The BuildBucket user agent.
	BbucketUserAgent string `bigquery:"bbucket_user_agent"`

	// An identifier unique to this build. Shared with 'build_id' in builds table.
	BuildId string `bigquery:"build_id"`

	// The time when the step started.
	StepStarted time.Time `bigquery:"step_started"`

	// The time when the step finished.
	StepFinished time.Time `bigquery:"step_finished"`
}
