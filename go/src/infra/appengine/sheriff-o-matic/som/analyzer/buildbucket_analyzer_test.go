package analyzer

import (
	"sort"
	"testing"

	. "github.com/smartystreets/goconvey/convey"
	bbpb "go.chromium.org/luci/buildbucket/proto"
	"golang.org/x/net/context"
	"infra/monitoring/messages"
)

type mockBuildBucket struct {
	ret []*bbpb.Build
	err error
}

func (bb *mockBuildBucket) LatestBuilds(ctx context.Context, builderIDs []*bbpb.BuilderID) ([]*bbpb.Build, error) {
	return bb.ret, bb.err
}

var (
	builderID = &bbpb.BuilderID{Project: "chromium", Bucket: "ci", Builder: "linux-rel"}
)

func TestBuildBucketAlerts(t *testing.T) {
	Convey("smoke", t, func() {
		a := New(0, 100)
		a.BuildBucket = &mockBuildBucket{
			ret: []*bbpb.Build{
				{
					Steps: []*bbpb.Step{
						{
							Name:   "a",
							Status: bbpb.Status_SUCCESS,
						},
					},
				},
			},
			err: nil,
		}
		ctx := context.Background()
		alerts, err := a.BuildBucketAlerts(ctx, []*bbpb.BuilderID{
			{Project: "chromium", Bucket: "ci", Builder: "linux-rel"},
		},
		)
		So(err, ShouldBeNil)
		So(alerts, ShouldBeEmpty)
	})

	Convey("single failure, single step", t, func() {
		a := New(0, 100)
		a.BuildBucket = &mockBuildBucket{
			ret: []*bbpb.Build{
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
				},
			},
			err: nil,
		}
		ctx := context.Background()
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

	Convey("multiple failures, single step", t, func() {
		a := New(0, 100)
		a.BuildBucket = &mockBuildBucket{
			ret: []*bbpb.Build{
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
				},
			},
			err: nil,
		}
		ctx := context.Background()
		failures, err := a.BuildBucketAlerts(ctx, []*bbpb.BuilderID{
			{Project: "chromium", Bucket: "ci", Builder: "linux-rel"},
		},
		)
		So(err, ShouldBeNil)
		So(failures, ShouldNotBeEmpty)
		So(failures[0].StepAtFault, ShouldNotBeNil)
		So(failures[0].StepAtFault.Step, ShouldNotBeNil)
		So(failures[0].StepAtFault.Step.Name, ShouldEqual, "step-name")

		So(failures[0].Builders, ShouldNotBeEmpty)
		So(failures[0].Builders[0].Name, ShouldEqual, "linux-rel")
		So(failures[0].Builders[0].FirstFailure, ShouldEqual, 8)
		So(failures[0].Builders[0].LatestFailure, ShouldEqual, 9)
	})

	Convey("multiple failures, multiple steps, step skipped in one build", t, func() {
		a := New(0, 100)
		a.BuildBucket = &mockBuildBucket{
			ret: []*bbpb.Build{
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
				},
			},
			err: nil,
		}
		ctx := context.Background()
		failures, err := a.BuildBucketAlerts(ctx, []*bbpb.BuilderID{
			{Project: "chromium", Bucket: "ci", Builder: "linux-rel"},
		},
		)
		So(err, ShouldBeNil)
		So(failures, ShouldNotBeEmpty)
		So(failures[0].StepAtFault, ShouldNotBeNil)
		So(failures[0].StepAtFault.Step, ShouldNotBeNil)
		So(failures[0].StepAtFault.Step.Name, ShouldEqual, "step-name")

		So(failures[0].Builders, ShouldNotBeEmpty)
		So(failures[0].Builders[0].Name, ShouldEqual, "linux-rel")
		So(failures[0].Builders[0].FirstFailure, ShouldEqual, 7)
		So(failures[0].Builders[0].LatestFailure, ShouldEqual, 9)
	})

	Convey("multiple failures, multiple steps", t, func() {
		a := New(0, 100)
		// This test case checks the following scenario for a single builder:
		// build : 9 8 7
		// -------------
		// step-a: F F P
		// step-b: F F F
		// step-c: P F F

		a.BuildBucket = &mockBuildBucket{
			ret: []*bbpb.Build{
				{
					// Build numbers on waterfall builders reflect source order.
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
				},
				{
					// Build numbers on waterfall builders reflect source order.
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
				},
				{
					// Build numbers on waterfall builders reflect source order.
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
				},
			},
			err: nil,
		}
		ctx := context.Background()
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

		So(failures[1].StepAtFault, ShouldNotBeNil)
		So(failures[1].StepAtFault.Step, ShouldNotBeNil)
		So(failures[1].StepAtFault.Step.Name, ShouldEqual, "step-b")
		So(len(failures[1].Builders), ShouldEqual, 1)
		So(failures[1].Builders[0].Name, ShouldEqual, "linux-rel")
		So(failures[1].Builders[0].FirstFailure, ShouldEqual, 7)
		So(failures[1].Builders[0].LatestFailure, ShouldEqual, 9)
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

		a.BuildBucket = &mockBuildBucket{
			ret: []*bbpb.Build{
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
				},
			},
			err: nil,
		}
		ctx := context.Background()
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
		So(alertedBuilders[1].Name, ShouldEqual, "b-rel")
		So(alertedBuilders[1].FirstFailure, ShouldEqual, 4)
		So(alertedBuilders[1].LatestFailure, ShouldEqual, 5)

		So(failures[1].StepAtFault, ShouldNotBeNil)
		So(failures[1].StepAtFault.Step, ShouldNotBeNil)
		So(failures[1].StepAtFault.Step.Name, ShouldEqual, "step-b")
		So(len(failures[1].Builders), ShouldEqual, 1)
		So(failures[1].Builders[0].Name, ShouldEqual, "a-rel")
		So(failures[1].Builders[0].FirstFailure, ShouldEqual, 7)
		So(failures[1].Builders[0].LatestFailure, ShouldEqual, 9)
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
