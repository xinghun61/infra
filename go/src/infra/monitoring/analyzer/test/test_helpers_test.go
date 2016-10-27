package test

import (
	"reflect"
	"testing"

	"infra/monitoring/messages"
)

func TestBuilderFaker(t *testing.T) {
	b := NewBuilderFaker("some master", "some builder")
	if b.BuilderName != "some builder" {
		t.Errorf("b.BuilderName isn't set")
	}
	b.Build(0)
	if len(b.Builds) != 1 {
		t.Errorf("Didn't create Build")
	}

	b.Build(0).IncludeChanges(
		"http://thing",
		"refs/heads/master@{1}",
		"refs/heads/master@{2}",
		"refs/heads/master@{3}",
		"refs/heads/master@{123}")

	if len(b.Builds["some master/some builder/0"].SourceStamp.Changes) != 4 {
		t.Errorf("Didn't create changes in SourceStamp")
	}

	b.Build(0).Step("bot update").Results(0)
	b.Build(0).Step("screw up git checkout").Results(2)

	if len(b.Builds["some master/some builder/0"].Steps) != 2 {
		t.Errorf("Didn't create steps")
	}

	if len(b.Builds["some master/some builder/0"].Steps[0].Results) != 1 {
		t.Errorf("Didn't create step results")
	}

	if len(b.Builds["some master/some builder/0"].Steps[1].Results) != 1 {
		t.Errorf("Did not create step results for second step")
	}

	b.Build(0).Times(0, 1, 2, 3)
	if len(b.Builds["some master/some builder/0"].Times) != 4 {
		t.Errorf("Didn't create times")
	}

	// All together now.
	bf := NewBuilderFaker("fake.master", "fake.builder").
		Build(0).Times(0, 1).IncludeChanges("http://repo", "refs/heads/master@{#291569}").
		Step("fake_step").Results(2).BuildFaker.
		Step("other step").Results(2).BuilderFaker
	expected := &messages.Build{
		Master:      "fake.master",
		BuilderName: "fake.builder",
		Number:      0,
		Times:       []messages.EpochTime{0, 1},
		Steps: []messages.Step{
			{
				Name:       "fake_step",
				IsFinished: true,
				Results:    []interface{}{float64(2)},
			},
			{
				Name:       "other step",
				IsFinished: true,
				Results:    []interface{}{float64(2)},
			},
		},
		SourceStamp: messages.SourceStamp{
			Changes: []messages.Change{
				{
					Repository: "http://repo",
					Revision:   "291569",
					Comments:   "some change comment\n\nCr-Commit-Position: refs/heads/master@{#291569}\n\n",
				},
			},
		},
	}

	got := bf.Builds["fake.master/fake.builder/0"]
	if !reflect.DeepEqual(got, expected) {
		t.Errorf("Didn't construct builds properly. Got \n\t%+v, want\n\t%+v", got, expected)
	}

	buildSteps := StepsAtFault(bf, []int{0, 0}, []string{"fake_step", "other step"})
	expectedSteps := []messages.BuildStep{
		{
			Master: &messages.MasterLocation{URL: *urlParse("https://build.chromium.org/p/fake.master")},
			Build:  expected,
			Step:   &expected.Steps[0],
		},
		{
			Master: &messages.MasterLocation{URL: *urlParse("https://build.chromium.org/p/fake.master")},
			Build:  expected,
			Step:   &expected.Steps[1],
		},
	}

	if !reflect.DeepEqual(buildSteps, expectedSteps) {
		t.Errorf("Didn't construct build steps properly. Got \n\t%+v, want\n\t%+v", buildSteps, expectedSteps)
	}

	if len(bf.GetBuilds()) != 1 {
		t.Errorf("GetBuilds returned wrong number of builds: Wanted 1, got %d", len(bf.GetBuilds()))
	}
}
