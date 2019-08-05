package analyzer

import (
	"testing"

	"infra/monitoring/messages"

	. "github.com/smartystreets/goconvey/convey"
)

func TestFilterHierarchicalSteps(t *testing.T) {
	Convey("smoke", t, func() {
		failures := []messages.BuildFailure{}
		got := filterHierarchicalSteps(failures)
		So(len(got), ShouldEqual, 0)
	})

	Convey("single step, single builder", t, func() {
		failures := []messages.BuildFailure{
			{
				Builders: []messages.AlertedBuilder{
					{
						Project: "project",
						Bucket:  "bucket",
						Name:    "builder name",
					},
				},
				StepAtFault: &messages.BuildStep{
					Step: &messages.Step{
						Name: "check build results",
					},
				},
			},
		}

		got := filterHierarchicalSteps(failures)
		So(len(got), ShouldEqual, 1)
		So(len(got[0].Builders), ShouldEqual, 1)
	})

	Convey("nested step, single builder", t, func() {
		failures := []messages.BuildFailure{
			{
				Builders: []messages.AlertedBuilder{
					{
						Project: "project",
						Bucket:  "bucket",
						Name:    "builder name A",
					},
				},
				StepAtFault: &messages.BuildStep{
					Step: &messages.Step{
						Name: "check build results",
					},
				},
			},
			{
				Builders: []messages.AlertedBuilder{
					{
						Project: "project",
						Bucket:  "bucket",
						Name:    "builder name A",
					},
				},
				StepAtFault: &messages.BuildStep{
					Step: &messages.Step{
						Name: "check build results|build results",
					},
				},
			},
			{
				Builders: []messages.AlertedBuilder{
					{
						Project: "project",
						Bucket:  "bucket",
						Name:    "builder name A",
					},
				},
				StepAtFault: &messages.BuildStep{
					Step: &messages.Step{
						Name: "check build results|build results|chromeos.postsubmit.beaglebone_servo-postsubmit",
					},
				},
			},
		}

		got := filterHierarchicalSteps(failures)
		So(len(got), ShouldEqual, 1)
		So(len(got[0].Builders), ShouldEqual, 1)
	})

	Convey("single step, multiple builders", t, func() {
		failures := []messages.BuildFailure{
			{
				Builders: []messages.AlertedBuilder{
					{
						Project: "project",
						Bucket:  "bucket",
						Name:    "builder name A",
					},
					{
						Project: "project",
						Bucket:  "bucket",
						Name:    "builder name B",
					},
				},
				StepAtFault: &messages.BuildStep{
					Step: &messages.Step{
						Name: "check build results",
					},
				},
			},
		}

		got := filterHierarchicalSteps(failures)
		So(len(got), ShouldEqual, 1)
		So(len(got[0].Builders), ShouldEqual, 2)
	})

	Convey("nested step, multiple builder", t, func() {
		failures := []messages.BuildFailure{
			{
				Builders: []messages.AlertedBuilder{
					{
						Project: "project",
						Bucket:  "bucket",
						Name:    "builder name A",
					},
					{
						Project: "project",
						Bucket:  "bucket",
						Name:    "builder name B",
					},
				},
				StepAtFault: &messages.BuildStep{
					Step: &messages.Step{
						Name: "check build results",
					},
				},
			},
			{
				Builders: []messages.AlertedBuilder{
					{
						Project: "project",
						Bucket:  "bucket",
						Name:    "builder name A",
					},
					{
						Project: "project",
						Bucket:  "bucket",
						Name:    "builder name B",
					},
				},
				StepAtFault: &messages.BuildStep{
					Step: &messages.Step{
						Name: "check build results|build results",
					},
				},
			},
			{
				Builders: []messages.AlertedBuilder{
					{
						Project: "project",
						Bucket:  "bucket",
						Name:    "builder name A",
					},
					{
						Project: "project",
						Bucket:  "bucket",
						Name:    "builder name B",
					},
				},
				StepAtFault: &messages.BuildStep{
					Step: &messages.Step{
						Name: "check build results|build results|chromeos.postsubmit.beaglebone_servo-postsubmit",
					},
				},
			},
		}

		got := filterHierarchicalSteps(failures)
		So(len(got), ShouldEqual, 1)
		So(len(got[0].Builders), ShouldEqual, 2)
		So(got[0].StepAtFault.Step.Name, ShouldEqual, "check build results|build results|chromeos.postsubmit.beaglebone_servo-postsubmit")
	})

	Convey("mixed nested steps, multiple builder", t, func() {
		failures := []messages.BuildFailure{
			{
				Builders: []messages.AlertedBuilder{
					{
						Project: "project",
						Bucket:  "bucket",
						Name:    "builder name A",
					},
					{
						Project: "project",
						Bucket:  "bucket",
						Name:    "builder name B",
					},
				},
				StepAtFault: &messages.BuildStep{
					Step: &messages.Step{
						Name: "check build results",
					},
				},
			},
			{
				Builders: []messages.AlertedBuilder{
					{
						Project: "project",
						Bucket:  "bucket",
						Name:    "builder name A",
					},
					{
						Project: "project",
						Bucket:  "bucket",
						Name:    "builder name B",
					},
				},
				StepAtFault: &messages.BuildStep{
					Step: &messages.Step{
						Name: "test foo",
					},
				},
			},
			{
				Builders: []messages.AlertedBuilder{
					{
						Project: "project",
						Bucket:  "bucket",
						Name:    "builder name A",
					},
				},
				StepAtFault: &messages.BuildStep{
					Step: &messages.Step{
						Name: "test bar",
					},
				},
			},
			{
				Builders: []messages.AlertedBuilder{
					{
						Project: "project",
						Bucket:  "bucket",
						Name:    "builder name B",
					},
				},
				StepAtFault: &messages.BuildStep{
					Step: &messages.Step{
						Name: "test baz",
					},
				},
			},
			{
				Builders: []messages.AlertedBuilder{
					{
						Project: "project",
						Bucket:  "bucket",
						Name:    "builder name A",
					},
					{
						Project: "project",
						Bucket:  "bucket",
						Name:    "builder name B",
					},
				},
				StepAtFault: &messages.BuildStep{
					Step: &messages.Step{
						Name: "check build results|build results",
					},
				},
			},
			{
				Builders: []messages.AlertedBuilder{
					{
						Project: "project",
						Bucket:  "bucket",
						Name:    "builder name A",
					},
					{
						Project: "project",
						Bucket:  "bucket",
						Name:    "builder name B",
					},
				},
				StepAtFault: &messages.BuildStep{
					Step: &messages.Step{
						Name: "check build results|build results|chromeos.postsubmit.beaglebone_servo-postsubmit",
					},
				},
			},
		}

		got := filterHierarchicalSteps(failures)
		So(len(got), ShouldEqual, 4)
		So(len(got[0].Builders), ShouldEqual, 2)
		So(got[0].StepAtFault.Step.Name, ShouldEqual, "test foo")
		So(len(got[1].Builders), ShouldEqual, 1)
		So(got[1].StepAtFault.Step.Name, ShouldEqual, "test bar")
		So(len(got[2].Builders), ShouldEqual, 1)
		So(got[2].StepAtFault.Step.Name, ShouldEqual, "test baz")
		So(len(got[3].Builders), ShouldEqual, 2)
		So(got[3].StepAtFault.Step.Name, ShouldEqual, "check build results|build results|chromeos.postsubmit.beaglebone_servo-postsubmit")
	})
}
