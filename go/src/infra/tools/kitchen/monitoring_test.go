// Copyright 2017 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package main

import (
	"encoding/json"
	"sync"
	"testing"
	"time"

	"infra/libs/bqschema/buildevent"
	"infra/tools/kitchen/build"

	"go.chromium.org/luci/common/clock/testclock"
	"go.chromium.org/luci/common/proto/google"
	"go.chromium.org/luci/common/proto/milo"

	"golang.org/x/net/context"

	. "github.com/smartystreets/goconvey/convey"
)

func TestMonitoring(t *testing.T) {
	t.Parallel()
	buildsTableKey := tableKey{datasetID: bqDatasetID, tableID: buildsTableID}
	stepsTableKey := tableKey{datasetID: bqDatasetID, tableID: stepsTableID}

	Convey(`A test BuildRunResult`, t, func() {
		ctx := context.Background()
		ctx, tc := testclock.UseTime(ctx, testclock.TestRecentTimeLocal)

		m := Monitoring{}

		// Pretend that we scheduled it 5 minutes prior to the build starting.
		sched := tc.Now().UTC()
		tc.Add(5 * time.Minute)
		m.beginExecution(ctx)

		var tmes testMonitoringEventSender

		Convey(`Without any build information, sends a sparse event.`, func() {
			tc.Add(time.Hour)
			m.endExecution(ctx, &build.BuildRunResult{})
			So(m.sendReport(ctx, &tmes), ShouldBeNil)
			So(tmes.events, ShouldResemble, localTable{
				buildsTableKey: {
					&buildevent.CompletedBuildsLegacy{
						BuildStartedMsec:   1454501406000,
						BuildFinishedMsec:  1454505006000,
						TotalDurationS:     3600,
						ExecutionDurationS: 3600,
						BuildStarted:       m.executionStart.UTC(),
						BuildFinished:      m.executionEnd.UTC(),
						Kitchen:            &buildevent.CompletedBuildsLegacy_Kitchen{},
					},
				},
				stepsTableKey: {
					[]*buildevent.CompletedStepLegacy(nil),
				},
			})
		})

		Convey(`With full build information, sends an event.`, func() {
			makeJSONString := func(v interface{}) string {
				d, err := json.Marshal(v)
				if err != nil {
					panic(err)
				}
				return string(d)
			}

			start := tc.Now().UTC()
			tc.Add(time.Hour)
			m.endExecution(ctx, &build.BuildRunResult{
				Recipe: &build.BuildRunResult_Recipe{
					Name:       "myrecipe",
					Repository: "https://example.com/recipes",
					Revision:   "deadbeef",
				},
				Annotations: &milo.Step{
					Status: milo.Status_SUCCESS,

					Command: &milo.Step_Command{
						Environ: map[string]string{
							"SWARMING_SERVER":  "https://example.com/swarming",
							"SWARMING_TASK_ID": "123450",
						},
					},

					Property: []*milo.Step_Property{
						{"buildbucket", makeJSONString(&buildBucketInfo{
							Hostname: "buildbucket.example.com",
							Build: buildBucketInfoBuild{
								Bucket:    "mybucket",
								CreatedTS: sched.UnixNano() / int64(time.Microsecond),
								ID:        "buildbucket-build-id",
								Tags: []string{
									"user_agent:my_user_agent",
								},
							},
						})},
						{"bot_id", `"my-bot"`},
						{"category", `"git_cl_try"`},
						{"mastername", `"buildbot.master"`},
						{"buildername", `"mybuilder"`},
						{"buildnumber", `1337`},
						{"patch_storage", `"gerrit"`},
						{"patch_gerrit_url", `"https://example.com/gerrit"`},
						{"patch_issue", `12345`},
						{"patch_set", `"42"`},
					},

					Substep: []*milo.Step_Substep{

						{Substep: &milo.Step_Substep_Step{
							Step: &milo.Step{
								Name:    "top-A",
								Status:  milo.Status_SUCCESS,
								Text:    []string{"foo", "bar", "baz"},
								Started: google.NewTimestamp(start.Add(5 * time.Minute)),
								Substep: []*milo.Step_Substep{

									{Substep: &milo.Step_Substep_Step{
										Step: &milo.Step{
											Name:   "inner",
											Status: milo.Status_FAILURE,
											FailureDetails: &milo.FailureDetails{
												Type: milo.FailureDetails_INFRA,
											},
											Started: google.NewTimestamp(start.Add(6 * time.Minute)),
											Ended:   google.NewTimestamp(start.Add(15 * time.Minute)),
										},
									}},
								},
								Ended: google.NewTimestamp(start.Add(20 * time.Minute)),
							},
						}},

						{Substep: &milo.Step_Substep_Step{
							Step: &milo.Step{
								Name:    "top-B",
								Status:  milo.Status_FAILURE,
								Text:    []string{"Top B"},
								Started: google.NewTimestamp(start.Add(25 * time.Minute)),
								Ended:   google.NewTimestamp(start.Add(30 * time.Minute)),
							},
						}},
					},
				},
			})

			So(m.sendReport(ctx, &tmes), ShouldBeNil)
			So(tmes.events, ShouldResemble, localTable{
				buildsTableKey: {
					&buildevent.CompletedBuildsLegacy{
						Master:             "buildbot.master",
						Builder:            "mybuilder",
						BuildNumber:        1337,
						BuildSchedMsec:     1454501106000,
						BuildStartedMsec:   1454501406000,
						BuildFinishedMsec:  1454505006000,
						HostName:           "my-bot",
						Result:             buildevent.ResultSuccess,
						QueueDurationS:     300.000000007,
						TotalDurationS:     3900.000000007,
						PatchUrl:           "https://example.com/gerrit/c/12345/42",
						Category:           buildevent.CategoryGitCLTry,
						ExecutionDurationS: 3600,
						BbucketId:          "buildbucket-build-id",
						BbucketUserAgent:   "my_user_agent",
						BuildId:            "buildbucket/buildbucket.example.com/buildbucket-build-id",
						BbucketBucket:      "mybucket",
						BuildScheduled:     sched.Round(time.Millisecond).UTC(),
						BuildStarted:       m.executionStart.UTC(),
						BuildFinished:      m.executionEnd.UTC(),
						Kitchen:            &buildevent.CompletedBuildsLegacy_Kitchen{},
						Recipes: &buildevent.CompletedBuildsLegacy_Recipes{
							Name:       "myrecipe",
							Repository: "https://example.com/recipes",
							Revision:   "deadbeef",
						},
						Swarming: &buildevent.CompletedBuildsLegacy_Swarming{
							Host:  "example.com",
							RunId: "123450",
						},
					},
				},

				stepsTableKey: {
					[]*buildevent.CompletedStepLegacy{
						{
							Master:           "buildbot.master",
							Builder:          "mybuilder",
							BuildNumber:      1337,
							BuildSchedMsec:   1454501106000,
							StepName:         "top-A",
							StepText:         "foo\nbar\nbaz",
							StepNumber:       0,
							HostName:         "my-bot",
							Result:           buildevent.ResultSuccess,
							StepStartedMsec:  1454501706000,
							StepDurationS:    900,
							PatchUrl:         "https://example.com/gerrit/c/12345/42",
							BbucketId:        "buildbucket-build-id",
							BbucketUserAgent: "my_user_agent",
							BuildId:          "buildbucket/buildbucket.example.com/buildbucket-build-id",
							StepStarted:      start.Add(5 * time.Minute).UTC(),
							StepFinished:     start.Add(20 * time.Minute).UTC(),
						},

						{
							Master:           "buildbot.master",
							Builder:          "mybuilder",
							BuildNumber:      1337,
							BuildSchedMsec:   1454501106000,
							StepName:         "inner",
							StepText:         "",
							StepNumber:       1,
							HostName:         "my-bot",
							Result:           buildevent.ResultInfraFailure,
							StepStartedMsec:  1454501766000,
							StepDurationS:    540,
							PatchUrl:         "https://example.com/gerrit/c/12345/42",
							BbucketId:        "buildbucket-build-id",
							BbucketUserAgent: "my_user_agent",
							BuildId:          "buildbucket/buildbucket.example.com/buildbucket-build-id",
							StepStarted:      start.Add(6 * time.Minute).UTC(),
							StepFinished:     start.Add(15 * time.Minute).UTC(),
						},

						{
							Master:           "buildbot.master",
							Builder:          "mybuilder",
							BuildNumber:      1337,
							BuildSchedMsec:   1454501106000,
							StepName:         "top-B",
							StepText:         "Top B",
							StepNumber:       2,
							HostName:         "my-bot",
							Result:           buildevent.ResultFailure,
							StepStartedMsec:  1454502906000,
							StepDurationS:    300,
							PatchUrl:         "https://example.com/gerrit/c/12345/42",
							BbucketId:        "buildbucket-build-id",
							BbucketUserAgent: "my_user_agent",
							BuildId:          "buildbucket/buildbucket.example.com/buildbucket-build-id",
							StepStarted:      start.Add(25 * time.Minute).UTC(),
							StepFinished:     start.Add(30 * time.Minute).UTC(),
						},
					},
				},
			})
		})
	})
}

type tableKey struct {
	datasetID, tableID string
}

type localTable map[tableKey][]interface{}

type testMonitoringEventSender struct {
	sync.Mutex
	events localTable
}

func (es *testMonitoringEventSender) Put(ctx context.Context, dID, tID string, event interface{}) error {
	es.Lock()
	defer es.Unlock()

	tk := tableKey{datasetID: dID, tableID: tID}

	if es.events == nil {
		es.events = make(localTable)
	}
	es.events[tk] = append(es.events[tk], event)
	return nil
}
