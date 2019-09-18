package analyzer

import (
	"cloud.google.com/go/bigquery"
	"google.golang.org/api/iterator"
	"testing"

	"infra/monitoring/messages"

	. "github.com/smartystreets/goconvey/convey"
)

type mockResults struct {
	failures []failureRow
	err      error
	curr     int
}

func (m *mockResults) Next(dst interface{}) error {
	if m.curr >= len(m.failures) {
		return iterator.Done
	}
	fdst := dst.(*failureRow)
	*fdst = m.failures[m.curr]
	m.curr++
	return m.err
}

func TestMockBQResults(t *testing.T) {
	Convey("no results", t, func() {
		mr := &mockResults{}
		r := &failureRow{}
		So(mr.Next(r), ShouldEqual, iterator.Done)
	})
	Convey("copy op works", t, func() {
		mr := &mockResults{
			failures: []failureRow{
				{
					StepName: "foo",
				},
			},
		}
		r := failureRow{}
		err := mr.Next(&r)
		So(err, ShouldBeNil)
		So(r.StepName, ShouldEqual, "foo")
		So(mr.Next(&r), ShouldEqual, iterator.Done)
	})

}

func TestProcessBQResults(t *testing.T) {
	Convey("smoke", t, func() {
		mr := &mockResults{}
		got, err := processBQResults(mr)
		So(err, ShouldEqual, nil)
		So(got, ShouldBeEmpty)
	})

	Convey("single result, only start/end build numbers", t, func() {
		mr := &mockResults{
			failures: []failureRow{
				{
					StepName: "some step",
					MasterName: bigquery.NullString{
						StringVal: "some master",
						Valid:     true,
					},
					Builder: "some builder",
					Project: "some project",
					Bucket:  "some bucket",
					BuildNumberBegin: bigquery.NullInt64{
						Int64: 1,
						Valid: true,
					},
					BuildNumberEnd: bigquery.NullInt64{
						Int64: 10,
						Valid: true,
					},
				},
			},
		}
		got, err := processBQResults(mr)
		So(err, ShouldEqual, nil)
		So(len(got), ShouldEqual, 1)
	})

	Convey("single result, only end build number", t, func() {
		mr := &mockResults{
			failures: []failureRow{
				{
					StepName: "some step",
					MasterName: bigquery.NullString{
						StringVal: "some master",
						Valid:     true,
					},
					Builder: "some builder",
					Project: "some project",
					Bucket:  "some bucket",
					BuildNumberEnd: bigquery.NullInt64{
						Int64: 10,
						Valid: true,
					},
				},
			},
		}
		got, err := processBQResults(mr)
		So(err, ShouldEqual, nil)
		So(len(got), ShouldEqual, 1)
	})
}

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
