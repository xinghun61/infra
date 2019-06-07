package analyzer

import (
	"sort"
	"testing"

	"infra/appengine/sheriff-o-matic/som/analyzer/step"
	"infra/appengine/sheriff-o-matic/som/client"

	"infra/monitoring/messages"

	"infra/appengine/test-results/model"

	structpb "github.com/golang/protobuf/ptypes/struct"
	. "github.com/smartystreets/goconvey/convey"
	"go.chromium.org/luci/appengine/gaetesting"
	bbpb "go.chromium.org/luci/buildbucket/proto"
	"go.chromium.org/luci/common/logging/gologger"
)

var (
	builderID = &bbpb.BuilderID{Project: "chromium", Bucket: "ci", Builder: "linux-rel"}
)

func inputProperties(master, builder, host, repo, hash string) *bbpb.Build_Input {
	return &bbpb.Build_Input{
		Properties: &structpb.Struct{
			Fields: map[string]*structpb.Value{
				"mastername":  {Kind: &structpb.Value_StringValue{StringValue: master}},
				"buildername": {Kind: &structpb.Value_StringValue{StringValue: master}},
			},
		},
		GitilesCommit: &bbpb.GitilesCommit{Host: host, Project: repo, Id: hash},
	}
}

func outputProperties(commitPos, rev string) *bbpb.Build_Output {
	return &bbpb.Build_Output{
		Properties: &structpb.Struct{
			Fields: map[string]*structpb.Value{
				"got_revision_cp": {Kind: &structpb.Value_StringValue{StringValue: commitPos}},
				"got_revision":    {Kind: &structpb.Value_StringValue{StringValue: rev}},
			},
		},
	}
}

func TestBuildBucketAlerts(t *testing.T) {
	Convey("smoke", t, func() {
		a := New(0, 100)
		a.BuildBucket = &client.StubBuildBucket{
			Latest: []*bbpb.Build{
				{
					Steps: []*bbpb.Step{
						{
							Name:   "a",
							Status: bbpb.Status_SUCCESS,
						},
					},
				},
			},
			Err: nil,
		}
		ctx := gaetesting.TestingContext()
		ctx = gologger.StdConfig.Use(ctx)
		alerts, err := a.BuildBucketAlerts(ctx, []*bbpb.BuilderID{
			{Project: "chromium", Bucket: "ci", Builder: "linux-rel"},
		},
		)
		So(err, ShouldBeNil)
		So(alerts, ShouldBeEmpty)
	})

	Convey("single failure, single step", t, func() {
		a := New(0, 100)
		a.BuildBucket = &client.StubBuildBucket{
			Latest: []*bbpb.Build{
				{
					Number: 42,
					Steps: []*bbpb.Step{
						{
							Name:   "step-name",
							Status: bbpb.Status_FAILURE,
						},
					},
					Builder: &bbpb.BuilderID{
						Builder: "linux-rel",
					},
					Input: inputProperties("some-master.foo", "linux-rel", "", "", ""),
				},
			},
			Err: nil,
		}
		ctx := gaetesting.TestingContext()
		ctx = gologger.StdConfig.Use(ctx)
		tr := &client.StubTestResults{}
		lr := &client.StubLogReader{}
		fi := &client.StubFindIt{}
		a.BuildBucketStepAnalyzers = step.DefaultBuildBucketStepAnalyzers(tr, lr, fi)
		a.FindIt = fi
		failures, err := a.BuildBucketAlerts(ctx, []*bbpb.BuilderID{builderID})
		So(err, ShouldBeNil)
		So(failures, ShouldNotBeEmpty)
		So(failures[0].StepAtFault, ShouldNotBeNil)
		So(failures[0].StepAtFault.Step, ShouldNotBeNil)
		So(failures[0].StepAtFault.Step.Name, ShouldEqual, "step-name")

		So(failures[0].Builders, ShouldNotBeEmpty)
		So(failures[0].Builders[0].Name, ShouldEqual, "linux-rel")
		So(failures[0].Builders[0].FirstFailure, ShouldEqual, 42)
		So(failures[0].Builders[0].LatestFailure, ShouldEqual, 42)
	})

	Convey("single failure, single step, multiple reasons", t, func() {
		a := New(0, 100)
		a.BuildBucket = &client.StubBuildBucket{
			Latest: []*bbpb.Build{
				{
					Number: 42,
					Steps: []*bbpb.Step{
						{
							Name:   "webkit_layout_tests",
							Status: bbpb.Status_FAILURE,
						},
					},
					Builder: &bbpb.BuilderID{
						Builder: "linux-rel",
					},
					Input: inputProperties("some-master.foo", "linux-rel", "", "", ""),
				},
			},
			Err: nil,
		}
		ctx := gaetesting.TestingContext()
		ctx = gologger.StdConfig.Use(ctx)
		truePtr := true
		tr := &client.StubTestResults{
			FullResult: &model.FullResult{
				Builder:     "linux-rel",
				BuildNumber: 42,
				Tests: model.FullTest{
					"some/test.html": &model.FullTestLeaf{
						Actual:     []string{"FAIL"},
						Expected:   []string{"PASS"},
						Unexpected: &truePtr,
					},
					"some-other/test.html": &model.FullTestLeaf{
						Actual:     []string{"FAIL"},
						Expected:   []string{"PASS"},
						Unexpected: &truePtr,
					},
				},
			},
		}
		lr := &client.StubLogReader{}
		fi := &client.StubFindIt{}
		a.BuildBucketStepAnalyzers = step.DefaultBuildBucketStepAnalyzers(tr, lr, fi)
		a.FindIt = fi
		failures, err := a.BuildBucketAlerts(ctx, []*bbpb.BuilderID{builderID})
		So(err, ShouldBeNil)
		So(len(failures), ShouldEqual, 1)

		So(failures[0].StepAtFault, ShouldNotBeNil)
		So(failures[0].StepAtFault.Step, ShouldNotBeNil)
		So(failures[0].StepAtFault.Step.Name, ShouldEqual, "webkit_layout_tests")
		So(failures[0].Reason.Kind(), ShouldEqual, "test")
		So(failures[0].Reason.Raw.Signature(), ShouldEqual, "some-other/test.html,some/test.html")

		testFailure, ok := failures[0].Reason.Raw.(*step.TestFailure)
		So(ok, ShouldBeTrue)
		So(len(testFailure.TestNames), ShouldEqual, 2)

		So(failures[0].Builders, ShouldNotBeEmpty)
		So(failures[0].Builders[0].Name, ShouldEqual, "linux-rel")
		So(failures[0].Builders[0].FirstFailure, ShouldEqual, 42)
		So(failures[0].Builders[0].LatestFailure, ShouldEqual, 42)
	})

	Convey("multiple failures, single step", t, func() {
		a := New(0, 100)
		a.BuildBucket = &client.StubBuildBucket{
			Latest: []*bbpb.Build{
				{
					// Build numbers on waterfall builders reflect source order.
					Number: 9,
					Steps: []*bbpb.Step{
						{
							Name:   "step-name",
							Status: bbpb.Status_FAILURE,
						},
					},
					Builder: &bbpb.BuilderID{
						Builder: "linux-rel",
					},
					Input:  inputProperties("some-master.foo", "linux-rel", "", "", ""),
					Output: outputProperties("refs/heads/master@{#3}", "deadbeef"),
				},
				{
					// Build numbers on waterfall builders reflect source order.
					Number: 8,
					Steps: []*bbpb.Step{
						{
							Name:   "step-name",
							Status: bbpb.Status_FAILURE,
						},
					},
					Builder: &bbpb.BuilderID{
						Builder: "linux-rel",
					},
					Input:  inputProperties("some-master.foo", "linux-rel", "", "", ""),
					Output: outputProperties("refs/heads/master@{#2}", "deadbeef"),
				},
				{
					// Build numbers on waterfall builders reflect source order.
					Number: 7,
					Steps: []*bbpb.Step{
						{
							Name:   "step-name",
							Status: bbpb.Status_SUCCESS,
						},
					},
					Builder: &bbpb.BuilderID{
						Builder: "linux-rel",
					},
					Input:  inputProperties("some-master.foo", "linux-rel", "", "", ""),
					Output: outputProperties("refs/heads/master@{#1}", "deadbeef"),
				},
			},
			Err: nil,
		}
		ctx := gaetesting.TestingContext()
		ctx = gologger.StdConfig.Use(ctx)
		tr := &client.StubTestResults{}
		lr := &client.StubLogReader{}
		fi := &client.StubFindIt{}
		a.BuildBucketStepAnalyzers = step.DefaultBuildBucketStepAnalyzers(tr, lr, fi)
		a.FindIt = fi
		failures, err := a.BuildBucketAlerts(ctx, []*bbpb.BuilderID{
			{Project: "chromium", Bucket: "ci", Builder: "linux-rel"},
		},
		)
		So(err, ShouldBeNil)
		So(len(failures), ShouldEqual, 1)
		So(failures[0].StepAtFault, ShouldNotBeNil)
		So(failures[0].StepAtFault.Step, ShouldNotBeNil)
		So(failures[0].StepAtFault.Step.Name, ShouldEqual, "step-name")

		So(failures[0].Builders, ShouldNotBeEmpty)
		So(failures[0].Builders[0].Name, ShouldEqual, "linux-rel")
		So(failures[0].Builders[0].FirstFailure, ShouldEqual, 8)
		So(failures[0].Builders[0].LatestFailure, ShouldEqual, 9)
		So(failures[0].Builders[0].FirstFailingRev.Position, ShouldEqual, 2)
		So(failures[0].Builders[0].LatestPassingRev.Position, ShouldEqual, 1)
	})

	Convey("multiple failures, single infra step", t, func() {
		a := New(0, 100)
		a.BuildBucket = &client.StubBuildBucket{
			Latest: []*bbpb.Build{
				{
					// Build numbers on waterfall builders reflect source order.
					Number: 9,
					Steps: []*bbpb.Step{
						{
							Name:   "step-name",
							Status: bbpb.Status_INFRA_FAILURE,
						},
					},
					Builder: &bbpb.BuilderID{
						Builder: "linux-rel",
					},
					Input:  inputProperties("some-master.foo", "linux-rel", "", "", ""),
					Output: outputProperties("refs/heads/master@{#3}", "deadbeef"),
				},
				{
					// Build numbers on waterfall builders reflect source order.
					Number: 8,
					Steps: []*bbpb.Step{
						{
							Name:   "step-name",
							Status: bbpb.Status_INFRA_FAILURE,
						},
					},
					Builder: &bbpb.BuilderID{
						Builder: "linux-rel",
					},
					Input:  inputProperties("some-master.foo", "linux-rel", "", "", ""),
					Output: outputProperties("refs/heads/master@{#2}", "deadbeef"),
				},
				{
					// Build numbers on waterfall builders reflect source order.
					Number: 7,
					Steps: []*bbpb.Step{
						{
							Name:   "step-name",
							Status: bbpb.Status_SUCCESS,
						},
					},
					Builder: &bbpb.BuilderID{
						Builder: "linux-rel",
					},
					Input:  inputProperties("some-master.foo", "linux-rel", "", "", ""),
					Output: outputProperties("refs/heads/master@{#1}", "deadbeef"),
				},
			},
			Err: nil,
		}
		ctx := gaetesting.TestingContext()
		ctx = gologger.StdConfig.Use(ctx)
		tr := &client.StubTestResults{}
		lr := &client.StubLogReader{}
		fi := &client.StubFindIt{}
		a.BuildBucketStepAnalyzers = step.DefaultBuildBucketStepAnalyzers(tr, lr, fi)
		a.FindIt = fi

		failures, err := a.BuildBucketAlerts(ctx, []*bbpb.BuilderID{
			{Project: "chromium", Bucket: "ci", Builder: "linux-rel"},
		},
		)
		So(err, ShouldBeNil)
		So(len(failures), ShouldEqual, 1)
		So(failures[0].StepAtFault, ShouldNotBeNil)
		So(failures[0].StepAtFault.Step, ShouldNotBeNil)
		So(failures[0].StepAtFault.Step.Name, ShouldEqual, "step-name")

		So(failures[0].Builders, ShouldNotBeEmpty)
		So(failures[0].Builders[0].Name, ShouldEqual, "linux-rel")
		So(failures[0].Builders[0].FirstFailure, ShouldEqual, 8)
		So(failures[0].Builders[0].LatestFailure, ShouldEqual, 9)
		So(failures[0].Builders[0].FirstFailingRev.Position, ShouldEqual, 2)
		So(failures[0].Builders[0].LatestPassingRev.Position, ShouldEqual, 1)
		So(failures[0].RegressionRanges[0].Repo, ShouldEqual, "chromium/src")
		So(failures[0].RegressionRanges[0].Host, ShouldEqual, "https://chromium.googlesource.com")
	})

	Convey("multiple failures, single failing step with others passing, failing step skipped in one build", t, func() {
		a := New(0, 100)
		a.BuildBucket = &client.StubBuildBucket{
			Latest: []*bbpb.Build{
				{
					Number: 9,
					Steps: []*bbpb.Step{
						{
							Name:   "step-name",
							Status: bbpb.Status_FAILURE,
						},
						{
							Name:   "other-step-name",
							Status: bbpb.Status_SUCCESS,
						},
					},
					Builder: &bbpb.BuilderID{
						Builder: "linux-rel",
					},
					Input:  inputProperties("some-master.foo", "linux-rel", "", "", ""),
					Output: outputProperties("refs/heads/master@{#3}", "deadbeef"),
				},
				{
					Number: 8,
					Steps: []*bbpb.Step{
						// Note that this time, step-name doesn't run at all.
						{
							Name:   "other-step-name",
							Status: bbpb.Status_FAILURE,
						},
					},
					Builder: &bbpb.BuilderID{
						Builder: "linux-rel",
					},
					Input:  inputProperties("some-master.foo", "linux-rel", "", "", ""),
					Output: outputProperties("refs/heads/master@{#2}", "deadbeef"),
				},
				{
					Number: 7,
					Steps: []*bbpb.Step{
						{
							Name:   "step-name",
							Status: bbpb.Status_FAILURE,
						},
					},
					Builder: &bbpb.BuilderID{
						Builder: "linux-rel",
					},
					Input:  inputProperties("some-master.foo", "linux-rel", "", "", ""),
					Output: outputProperties("refs/heads/master@{#1}", "deadbeef"),
				},
				// TODO: add a test case where there has never been a passing
				// run of "step-name". Currently that fails.
				{
					Number: 6,
					Steps: []*bbpb.Step{
						{
							Name:   "step-name",
							Status: bbpb.Status_SUCCESS,
						},
					},
					Builder: &bbpb.BuilderID{
						Builder: "linux-rel",
					},
					Input:  inputProperties("some-master.foo", "linux-rel", "", "", ""),
					Output: outputProperties("refs/heads/master@{#0}", "deadbeef"),
				},
			},
			Err: nil,
		}
		ctx := gaetesting.TestingContext()
		ctx = gologger.StdConfig.Use(ctx)
		tr := &client.StubTestResults{}
		lr := &client.StubLogReader{}
		fi := &client.StubFindIt{}
		a.BuildBucketStepAnalyzers = step.DefaultBuildBucketStepAnalyzers(tr, lr, fi)
		a.FindIt = fi

		failures, err := a.BuildBucketAlerts(ctx, []*bbpb.BuilderID{
			{Project: "chromium", Bucket: "ci", Builder: "linux-rel"},
		},
		)
		So(err, ShouldBeNil)
		So(len(failures), ShouldEqual, 1)
		So(failures[0].StepAtFault, ShouldNotBeNil)
		So(failures[0].StepAtFault.Step, ShouldNotBeNil)
		So(failures[0].StepAtFault.Step.Name, ShouldEqual, "step-name")

		So(failures[0].Builders, ShouldNotBeEmpty)
		So(failures[0].Builders[0].Name, ShouldEqual, "linux-rel")
		So(failures[0].Builders[0].FirstFailure, ShouldEqual, 7)
		So(failures[0].Builders[0].LatestFailure, ShouldEqual, 9)
		So(failures[0].Builders[0].FirstFailingRev.Position, ShouldEqual, 1)
		So(failures[0].Builders[0].LatestPassingRev.Position, ShouldEqual, 0)
	})

	Convey("multiple failures, multiple steps", t, func() {
		a := New(0, 100)
		// This test case checks the following scenario for a single builder:
		// build : 9 8 7
		// -------------
		// step-a: F F P
		// step-b: F F F
		// step-c: P F F

		a.BuildBucket = &client.StubBuildBucket{
			Latest: []*bbpb.Build{
				{
					Number: 9,
					Steps: []*bbpb.Step{
						{
							Name:   "step-a",
							Status: bbpb.Status_FAILURE,
						},
						{
							Name:   "step-b",
							Status: bbpb.Status_FAILURE,
						},
						{
							Name:   "step-c",
							Status: bbpb.Status_SUCCESS,
						},
					},
					Builder: &bbpb.BuilderID{
						Builder: "linux-rel",
					},
					Input:  inputProperties("some-master.foo", "linux-rel", "", "", ""),
					Output: outputProperties("refs/heads/master@{#3}", "deadbeef"),
				},
				{
					Number: 8,
					Steps: []*bbpb.Step{
						{
							Name:   "step-a",
							Status: bbpb.Status_FAILURE,
						},
						{
							Name:   "step-b",
							Status: bbpb.Status_FAILURE,
						},
						{
							Name:   "step-c",
							Status: bbpb.Status_FAILURE,
						},
					},
					Builder: &bbpb.BuilderID{
						Builder: "linux-rel",
					},
					Input:  inputProperties("some-master.foo", "linux-rel", "", "", ""),
					Output: outputProperties("refs/heads/master@{#2}", "deadbeef"),
				},
				{
					Number: 7,
					Steps: []*bbpb.Step{
						{
							Name:   "step-a",
							Status: bbpb.Status_SUCCESS,
						},
						{
							Name:   "step-b",
							Status: bbpb.Status_FAILURE,
						},
						{
							Name:   "step-c",
							Status: bbpb.Status_FAILURE,
						},
					},
					Builder: &bbpb.BuilderID{
						Builder: "linux-rel",
					},
					Input:  inputProperties("some-master.foo", "linux-rel", "", "", ""),
					Output: outputProperties("refs/heads/master@{#1}", "deadbeef"),
				},
				{
					Number: 6,
					Steps: []*bbpb.Step{
						{
							Name:   "step-a",
							Status: bbpb.Status_SUCCESS,
						},
						{
							Name:   "step-b",
							Status: bbpb.Status_SUCCESS,
						},
						{
							Name:   "step-c",
							Status: bbpb.Status_SUCCESS,
						},
					},
					Builder: &bbpb.BuilderID{
						Builder: "linux-rel",
					},
					Input:  inputProperties("some-master.foo", "linux-rel", "", "", ""),
					Output: outputProperties("refs/heads/master@{#0}", "deadbeef"),
				},
			},
			Err: nil,
		}
		ctx := gaetesting.TestingContext()
		ctx = gologger.StdConfig.Use(ctx)
		tr := &client.StubTestResults{}
		lr := &client.StubLogReader{}
		fi := &client.StubFindIt{}
		a.BuildBucketStepAnalyzers = step.DefaultBuildBucketStepAnalyzers(tr, lr, fi)
		a.FindIt = fi

		failures, err := a.BuildBucketAlerts(ctx, []*bbpb.BuilderID{
			{Project: "chromium", Bucket: "ci", Builder: "linux-rel"},
		},
		)
		// Sort these so the test doesn't flake.
		sort.Sort(buildFailuresByStepName(failures))

		So(err, ShouldBeNil)
		So(len(failures), ShouldEqual, 2)

		So(failures[0].StepAtFault, ShouldNotBeNil)
		So(failures[0].StepAtFault.Step, ShouldNotBeNil)
		So(failures[0].StepAtFault.Step.Name, ShouldEqual, "step-a")
		So(len(failures[0].Builders), ShouldEqual, 1)
		So(failures[0].Builders[0].Name, ShouldEqual, "linux-rel")
		So(failures[0].Builders[0].FirstFailure, ShouldEqual, 8)
		So(failures[0].Builders[0].LatestFailure, ShouldEqual, 9)
		So(failures[0].Builders[0].FirstFailingRev.Position, ShouldEqual, 2)
		So(failures[0].Builders[0].LatestPassingRev.Position, ShouldEqual, 1)

		So(failures[1].StepAtFault, ShouldNotBeNil)
		So(failures[1].StepAtFault.Step, ShouldNotBeNil)
		So(failures[1].StepAtFault.Step.Name, ShouldEqual, "step-b")
		So(len(failures[1].Builders), ShouldEqual, 1)
		So(failures[1].Builders[0].Name, ShouldEqual, "linux-rel")
		So(failures[1].Builders[0].FirstFailure, ShouldEqual, 7)
		So(failures[1].Builders[0].LatestFailure, ShouldEqual, 9)
		So(failures[1].Builders[0].FirstFailingRev.Position, ShouldEqual, 1)
		So(failures[1].Builders[0].LatestPassingRev.Position, ShouldEqual, 0)
	})

	Convey("multiple failures, multiple steps, multiple builders", t, func() {
		a := New(0, 100)
		// This test case checks the following scenario for builder a:
		// build : 9 8 7
		// -------------
		// step-a: F F P
		// step-b: F F F
		// step-c: P F F

		// And for builder b:
		// build : 5 4 3
		// -------------
		// step-a: F F P
		// step-b: P F F
		// step-c: P F F

		a.BuildBucket = &client.StubBuildBucket{
			Latest: []*bbpb.Build{
				{
					Number: 9,
					Steps: []*bbpb.Step{
						{
							Name:   "step-a",
							Status: bbpb.Status_FAILURE,
						},
						{
							Name:   "step-b",
							Status: bbpb.Status_FAILURE,
						},
						{
							Name:   "step-c",
							Status: bbpb.Status_SUCCESS,
						},
					},
					Builder: &bbpb.BuilderID{
						Builder: "a-rel",
					},
					Input:  inputProperties("some-master.foo", "a-rel", "", "", ""),
					Output: outputProperties("refs/heads/master@{#32}", "deadbeef"),
				},
				{
					Number: 5,
					Steps: []*bbpb.Step{
						{
							Name:   "step-a",
							Status: bbpb.Status_FAILURE,
						},
						{
							Name:   "step-b",
							Status: bbpb.Status_SUCCESS,
						},
						{
							Name:   "step-c",
							Status: bbpb.Status_SUCCESS,
						},
					},
					Builder: &bbpb.BuilderID{
						Builder: "b-rel",
					},
					Input:  inputProperties("some-master.foo", "b-rel", "", "", ""),
					Output: outputProperties("refs/heads/master@{#31}", "deadbeef"),
				},
				{
					Number: 8,
					Steps: []*bbpb.Step{
						{
							Name:   "step-a",
							Status: bbpb.Status_FAILURE,
						},
						{
							Name:   "step-b",
							Status: bbpb.Status_FAILURE,
						},
						{
							Name:   "step-c",
							Status: bbpb.Status_FAILURE,
						},
					},
					Builder: &bbpb.BuilderID{
						Builder: "a-rel",
					},
					Input:  inputProperties("some-master.foo", "a-rel", "", "", ""),
					Output: outputProperties("refs/heads/master@{#23}", "deadbeef"),
				},
				{
					Number: 4,
					Steps: []*bbpb.Step{
						{
							Name:   "step-a",
							Status: bbpb.Status_FAILURE,
						},
						{
							Name:   "step-b",
							Status: bbpb.Status_FAILURE,
						},
						{
							Name:   "step-c",
							Status: bbpb.Status_FAILURE,
						},
					},
					Builder: &bbpb.BuilderID{
						Builder: "b-rel",
					},
					Input:  inputProperties("some-master.foo", "b-rel", "", "", ""),
					Output: outputProperties("refs/heads/master@{#22}", "deadbeef"),
				},
				{
					Number: 7,
					Steps: []*bbpb.Step{
						{
							Name:   "step-a",
							Status: bbpb.Status_SUCCESS,
						},
						{
							Name:   "step-b",
							Status: bbpb.Status_FAILURE,
						},
						{
							Name:   "step-c",
							Status: bbpb.Status_FAILURE,
						},
					},
					Builder: &bbpb.BuilderID{
						Builder: "a-rel",
					},
					Input:  inputProperties("some-master.foo", "a-rel", "", "", ""),
					Output: outputProperties("refs/heads/master@{#12}", "deadbeef"),
				},
				{
					Number: 3,
					Steps: []*bbpb.Step{
						{
							Name:   "step-a",
							Status: bbpb.Status_SUCCESS,
						},
						{
							Name:   "step-b",
							Status: bbpb.Status_FAILURE,
						},
						{
							Name:   "step-c",
							Status: bbpb.Status_FAILURE,
						},
					},
					Builder: &bbpb.BuilderID{
						Builder: "b-rel",
					},
					Input:  inputProperties("some-master.foo", "b-rel", "", "", ""),
					Output: outputProperties("refs/heads/master@{#11}", "deadbeef"),
				},
				{
					Number: 6,
					Steps: []*bbpb.Step{
						{
							Name:   "step-a",
							Status: bbpb.Status_SUCCESS,
						},
						{
							Name:   "step-b",
							Status: bbpb.Status_SUCCESS,
						},
						{
							Name:   "step-c",
							Status: bbpb.Status_SUCCESS,
						},
					},
					Builder: &bbpb.BuilderID{
						Builder: "a-rel",
					},
					Input:  inputProperties("some-master.foo", "a-rel", "", "", ""),
					Output: outputProperties("refs/heads/master@{#2}", "deadbeef"),
				},
				{
					Number: 2,
					Steps: []*bbpb.Step{
						{
							Name:   "step-a",
							Status: bbpb.Status_SUCCESS,
						},
						{
							Name:   "step-b",
							Status: bbpb.Status_SUCCESS,
						},
						{
							Name:   "step-c",
							Status: bbpb.Status_SUCCESS,
						},
					},
					Builder: &bbpb.BuilderID{
						Builder: "b-rel",
					},
					Input:  inputProperties("some-master.foo", "b-rel", "", "", ""),
					Output: outputProperties("refs/heads/master@{#1}", "deadbeef"),
				},
			},
			Err: nil,
		}
		ctx := gaetesting.TestingContext()
		ctx = gologger.StdConfig.Use(ctx)
		tr := &client.StubTestResults{}
		lr := &client.StubLogReader{}
		fi := &client.StubFindIt{}
		a.BuildBucketStepAnalyzers = step.DefaultBuildBucketStepAnalyzers(tr, lr, fi)
		a.FindIt = fi

		failures, err := a.BuildBucketAlerts(ctx, []*bbpb.BuilderID{
			{Project: "chromium", Bucket: "ci", Builder: "a-rel"},
			{Project: "chromium", Bucket: "ci", Builder: "b-rel"},
		},
		)
		// Sort these so the test doesn't flake.
		sort.Sort(buildFailuresByStepName(failures))

		So(err, ShouldBeNil)
		So(len(failures), ShouldEqual, 2)

		So(failures[0].StepAtFault, ShouldNotBeNil)
		So(failures[0].StepAtFault.Step, ShouldNotBeNil)
		So(failures[0].StepAtFault.Step.Name, ShouldEqual, "step-a")
		So(len(failures[0].Builders), ShouldEqual, 2)

		// Sort AlertedBuilders so the test doesn't flake.
		alertedBuilders := failures[0].Builders
		sort.Sort(buildersByName(alertedBuilders))
		So(alertedBuilders[0].Name, ShouldEqual, "a-rel")
		So(alertedBuilders[0].FirstFailure, ShouldEqual, 8)
		So(alertedBuilders[0].LatestFailure, ShouldEqual, 9)
		So(alertedBuilders[0].FirstFailingRev.Position, ShouldEqual, 23)
		So(alertedBuilders[0].LatestPassingRev.Position, ShouldEqual, 12)

		So(alertedBuilders[1].Name, ShouldEqual, "b-rel")
		So(alertedBuilders[1].FirstFailure, ShouldEqual, 4)
		So(alertedBuilders[1].LatestFailure, ShouldEqual, 5)
		So(alertedBuilders[1].FirstFailingRev.Position, ShouldEqual, 22)
		So(alertedBuilders[1].LatestPassingRev.Position, ShouldEqual, 11)

		So(failures[1].StepAtFault, ShouldNotBeNil)
		So(failures[1].StepAtFault.Step, ShouldNotBeNil)
		So(failures[1].StepAtFault.Step.Name, ShouldEqual, "step-b")
		So(len(failures[1].Builders), ShouldEqual, 1)

		alertedBuilders = failures[1].Builders
		sort.Sort(buildersByName(alertedBuilders))

		So(alertedBuilders[0].Name, ShouldEqual, "a-rel")
		So(alertedBuilders[0].FirstFailure, ShouldEqual, 7)
		So(alertedBuilders[0].LatestFailure, ShouldEqual, 9)
		So(alertedBuilders[0].FirstFailingRev.Position, ShouldEqual, 12)
		So(alertedBuilders[0].LatestPassingRev.Position, ShouldEqual, 2)
	})

	Convey("Filter nested steps", t, func() {
		Convey("Non-nested case, despite prefix matches", func() {
			steps := []*bbpb.Step{
				{
					Name:   "step-name",
					Status: bbpb.Status_FAILURE,
				},
				{
					Name:   "step-name nested-step-name",
					Status: bbpb.Status_FAILURE,
				},
				{
					Name:   "step-name nested-step-name really-nested-step-name",
					Status: bbpb.Status_FAILURE,
				},
			}
			got := filterNestedSteps(steps)
			So(len(got), ShouldEqual, 3)
		})

		Convey("Simple nested case", func() {
			steps := []*bbpb.Step{
				{
					Name:   "step-name",
					Status: bbpb.Status_FAILURE,
				},
				{
					Name:   "step-name|nested-step-name",
					Status: bbpb.Status_FAILURE,
				},
				{
					Name:   "step-name|nested-step-name|really-nested-step-name",
					Status: bbpb.Status_FAILURE,
				},
			}
			got := filterNestedSteps(steps)
			So(len(got), ShouldEqual, 1)
		})

		Convey("Nested, with siblings", func() {
			steps := []*bbpb.Step{
				{
					Name:   "step-name",
					Status: bbpb.Status_FAILURE,
				},
				{
					Name:   "step-name|nested-step-name",
					Status: bbpb.Status_FAILURE,
				},
				{
					Name:   "step-name|nested-step-name|really-nested-step-name",
					Status: bbpb.Status_FAILURE,
				},
				{
					Name:   "step-name|nested-step-name|really-nested-sibling-step-name",
					Status: bbpb.Status_FAILURE,
				},
				{
					Name:   "step-name|nested-step-name|really-nested-sibling-step-name-3",
					Status: bbpb.Status_FAILURE,
				},
			}
			got := filterNestedSteps(steps)
			So(len(got), ShouldEqual, 3)
			So(got[0].Name, ShouldEqual, "step-name|nested-step-name|really-nested-step-name")
			So(got[1].Name, ShouldEqual, "step-name|nested-step-name|really-nested-sibling-step-name")
			So(got[2].Name, ShouldEqual, "step-name|nested-step-name|really-nested-sibling-step-name-3")
		})

		Convey("Mixed nested, non-nested case, end on non-nested", func() {
			steps := []*bbpb.Step{
				{
					Name:   "first-step-name",
					Status: bbpb.Status_FAILURE,
				},
				{
					Name:   "step-name",
					Status: bbpb.Status_FAILURE,
				},
				{
					Name:   "step-name|nested-step-name",
					Status: bbpb.Status_FAILURE,
				},
				{
					Name:   "step-name|nested-step-name|really-nested-step-name",
					Status: bbpb.Status_FAILURE,
				},
				{
					Name:   "last-step-name",
					Status: bbpb.Status_FAILURE,
				},
			}
			got := filterNestedSteps(steps)
			So(len(got), ShouldEqual, 3)
			So(got[0].Name, ShouldEqual, "first-step-name")
			So(got[1].Name, ShouldEqual, "step-name|nested-step-name|really-nested-step-name")
			So(got[2].Name, ShouldEqual, "last-step-name")
		})

		Convey("Mixed nested, non-nested case, end on nested", func() {
			steps := []*bbpb.Step{
				{
					Name:   "first-step-name",
					Status: bbpb.Status_FAILURE,
				},
				{
					Name:   "step-name",
					Status: bbpb.Status_FAILURE,
				},
				{
					Name:   "step-name|nested-step-name",
					Status: bbpb.Status_FAILURE,
				},
				{
					Name:   "step-name|nested-step-name|really-nested-step-name",
					Status: bbpb.Status_FAILURE,
				},
			}
			got := filterNestedSteps(steps)
			So(len(got), ShouldEqual, 2)
			So(got[0].Name, ShouldEqual, "first-step-name")
			So(got[1].Name, ShouldEqual, "step-name|nested-step-name|really-nested-step-name")
		})

		Convey("Mixed nested, non-nested case, start on nested", func() {
			steps := []*bbpb.Step{
				{
					Name:   "step-name",
					Status: bbpb.Status_FAILURE,
				},
				{
					Name:   "step-name|nested-step-name",
					Status: bbpb.Status_FAILURE,
				},
				{
					Name:   "step-name|nested-step-name|really-nested-step-name",
					Status: bbpb.Status_FAILURE,
				},
				{
					Name:   "last-step-name",
					Status: bbpb.Status_FAILURE,
				},
			}
			got := filterNestedSteps(steps)
			So(len(got), ShouldEqual, 2)
			So(got[0].Name, ShouldEqual, "step-name|nested-step-name|really-nested-step-name")
			So(got[1].Name, ShouldEqual, "last-step-name")
		})
	})

	Convey("Nested steps", t, func() {
		a := New(0, 100)
		a.BuildBucket = &client.StubBuildBucket{
			Latest: []*bbpb.Build{
				{
					Number: 42,
					Steps: []*bbpb.Step{
						{
							Name:   "step-name",
							Status: bbpb.Status_FAILURE,
						},
						{
							Name:   "step-name|nested-step-name",
							Status: bbpb.Status_FAILURE,
						},
						{
							Name:   "step-name|nested-step-name|really-nested-step-name",
							Status: bbpb.Status_FAILURE,
						},
					},
					Builder: &bbpb.BuilderID{
						Builder: "linux-rel",
					},
					Input: inputProperties("some-master.foo", "linux-rel", "", "", ""),
				},
			},
			Err: nil,
		}
		ctx := gaetesting.TestingContext()
		ctx = gologger.StdConfig.Use(ctx)
		tr := &client.StubTestResults{}
		lr := &client.StubLogReader{}
		fi := &client.StubFindIt{}
		a.BuildBucketStepAnalyzers = step.DefaultBuildBucketStepAnalyzers(tr, lr, fi)
		a.FindIt = fi
		failures, err := a.BuildBucketAlerts(ctx, []*bbpb.BuilderID{builderID})
		So(err, ShouldBeNil)
		So(failures, ShouldNotBeEmpty)
		So(failures[0].StepAtFault, ShouldNotBeNil)
		So(failures[0].StepAtFault.Step, ShouldNotBeNil)
		So(failures[0].StepAtFault.Step.Name, ShouldEqual,
			"step-name|nested-step-name|really-nested-step-name")

		So(failures[0].Builders, ShouldNotBeEmpty)
		So(failures[0].Builders[0].Name, ShouldEqual, "linux-rel")
		So(failures[0].Builders[0].FirstFailure, ShouldEqual, 42)
		So(failures[0].Builders[0].LatestFailure, ShouldEqual, 42)

	})

	Convey("missing output info filled with input info", t, func() {
		a := New(0, 100)
		a.BuildBucket = &client.StubBuildBucket{
			Latest: []*bbpb.Build{
				{
					// Build numbers on waterfall builders reflect source order.
					Number: 9,
					Steps: []*bbpb.Step{
						{
							Name:   "step-name",
							Status: bbpb.Status_FAILURE,
						},
					},
					Builder: &bbpb.BuilderID{
						Builder: "linux-rel",
					},
					Input: inputProperties(
						"some-master.foo", "linux-rel", "http://chrome-internal.googlesource.com", "chromeos/test", "abc123"),
					Output: outputProperties("", ""),
				},
				{
					// Build numbers on waterfall builders reflect source order.
					Number: 8,
					Steps: []*bbpb.Step{
						{
							Name:   "step-name",
							Status: bbpb.Status_FAILURE,
						},
					},
					Builder: &bbpb.BuilderID{
						Builder: "linux-rel",
					},
					Input:  inputProperties("some-master.foo", "linux-rel", "http://chrome-internal.googlesource.com", "chromeos/test", "abc122"),
					Output: outputProperties("", ""),
				},
				{
					// Build numbers on waterfall builders reflect source order.
					Number: 7,
					Steps: []*bbpb.Step{
						{
							Name:   "step-name",
							Status: bbpb.Status_SUCCESS,
						},
					},
					Builder: &bbpb.BuilderID{
						Builder: "linux-rel",
					},
					Input:  inputProperties("some-master.foo", "linux-rel", "http://chrome-internal.googlesource.com", "chromeos/test", "abc121"),
					Output: outputProperties("", ""),
				},
			},
		}
		ctx := gaetesting.TestingContext()
		ctx = gologger.StdConfig.Use(ctx)
		tr := &client.StubTestResults{}
		lr := &client.StubLogReader{}
		fi := &client.StubFindIt{}
		a.BuildBucketStepAnalyzers = step.DefaultBuildBucketStepAnalyzers(tr, lr, fi)
		a.FindIt = fi
		failures, err := a.BuildBucketAlerts(ctx, []*bbpb.BuilderID{builderID})
		So(err, ShouldBeNil)
		So(failures, ShouldNotBeEmpty)
		So(len(failures), ShouldEqual, 1)
		So(failures[0].Builders, ShouldNotBeEmpty)
		So(failures[0].Builders[0].FirstFailure, ShouldEqual, 8)
		So(failures[0].Builders[0].LatestFailure, ShouldEqual, 9)
		So(failures[0].Builders[0].FirstFailingRev.Position, ShouldEqual, 0)
		So(failures[0].Builders[0].FirstFailingRev.GitHash, ShouldEqual, "abc122")
		So(failures[0].Builders[0].LatestPassingRev.Position, ShouldEqual, 0)
		So(failures[0].Builders[0].LatestPassingRev.GitHash, ShouldEqual, "abc121")
		So(failures[0].RegressionRanges[0].Revisions, ShouldResemble, []string{"abc121", "abc122"})
		So(failures[0].RegressionRanges[0].Repo, ShouldEqual, "chromeos/test")
		So(failures[0].RegressionRanges[0].Host, ShouldEqual, "http://chrome-internal.googlesource.com")
	})
}

type buildersByName []messages.AlertedBuilder

func (a buildersByName) Len() int      { return len(a) }
func (a buildersByName) Swap(i, j int) { a[i], a[j] = a[j], a[i] }
func (a buildersByName) Less(i, j int) bool {
	return a[i].Name < a[j].Name
}

type buildFailuresByStepName []messages.BuildFailure

func (a buildFailuresByStepName) Len() int      { return len(a) }
func (a buildFailuresByStepName) Swap(i, j int) { a[i], a[j] = a[j], a[i] }
func (a buildFailuresByStepName) Less(i, j int) bool {
	return a[i].StepAtFault.Step.Name < a[j].StepAtFault.Step.Name
}

type alertsByStepName []messages.Alert

func (a alertsByStepName) Len() int      { return len(a) }
func (a alertsByStepName) Swap(i, j int) { a[i], a[j] = a[j], a[i] }
func (a alertsByStepName) Less(i, j int) bool {
	return a[i].Extension.(messages.BuildFailure).StepAtFault.Step.Name < a[j].Extension.(messages.BuildFailure).StepAtFault.Step.Name
}
