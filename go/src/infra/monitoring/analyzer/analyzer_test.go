// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package analyzer

import (
	"fmt"
	"net/url"
	"reflect"
	"sort"
	"testing"
	"time"

	"infra/libs/testing/ansidiff"
	analyzertest "infra/monitoring/analyzer/test"
	"infra/monitoring/client"
	clientTest "infra/monitoring/client/test"
	"infra/monitoring/messages"

	. "github.com/smartystreets/goconvey/convey"
)

func fakeNow(t time.Time) func() time.Time {
	return func() time.Time {
		return t
	}
}

func urlParse(s string, t *testing.T) *url.URL {
	p, err := url.Parse(s)
	if err != nil {
		t.Errorf("failed to parse %s: %s", s, err)
	}
	return p
}

type fakeReasonRaw struct {
	signature string
}

func (f *fakeReasonRaw) Signature() string {
	if f.signature != "" {
		return f.signature
	}

	return "fakeSignature"
}

func (f *fakeReasonRaw) Kind() string {
	return "fakeKind"
}

func (f *fakeReasonRaw) Title([]*messages.BuildStep) string {
	return "fakeTitle"
}

type fakeAnalyzer struct {
}

func (f *fakeAnalyzer) Analyze(reader client.Reader, failures []*messages.BuildStep) []messages.ReasonRaw {
	return fakeFinder(reader, failures)
}

func fakeFinder(Reader client.Reader, failures []*messages.BuildStep) []messages.ReasonRaw {
	raws := make([]messages.ReasonRaw, len(failures))
	for i := range failures {
		raws[i] = &fakeReasonRaw{}
	}
	return raws
}

func newTestAnalyzer(c client.Reader, minBuilds, maxBuilds int) *Analyzer {
	a := New(c, minBuilds, maxBuilds)
	a.reasonFinder = fakeFinder
	return a
}

func TestMasterAlerts(t *testing.T) {
	tests := []struct {
		name   string
		master string
		be     messages.BuildExtract
		t      time.Time
		want   []messages.Alert
	}{
		{
			name:   "empty",
			master: "fake-empty",
			want:   []messages.Alert{},
		},
		{
			name:   "Not stale master",
			master: "fake-not-stale",
			be: messages.BuildExtract{
				CreatedTimestamp: messages.EpochTime(100),
			},
			t:    time.Unix(100, 0),
			want: []messages.Alert{},
		},
		{
			name:   "Stale master",
			master: "fake.master",
			be: messages.BuildExtract{
				CreatedTimestamp: messages.EpochTime(100),
			},
			t: time.Unix(100, 0).Add(20 * time.Minute),
			want: []messages.Alert{
				{
					Key:       "stale master: https://build.chromium.org/p/fake.master",
					Title:     "Stale https://build.chromium.org/p/fake.master master data",
					Type:      messages.AlertStaleMaster,
					Severity:  staleMasterSev,
					Body:      "0h 20m elapsed since last update.",
					Time:      messages.TimeToEpochTime(time.Unix(100, 0).Add(20 * time.Minute)),
					Links:     []messages.Link{{"Master", urlParse("https://build.chromium.org/p/fake.master", t).String()}},
					StartTime: messages.EpochTime(100),
				},
			},
		},
		{
			name:   "Future master",
			master: "fake.master",
			be: messages.BuildExtract{
				CreatedTimestamp: messages.EpochTime(110),
			},
			t:    time.Unix(100, 0),
			want: []messages.Alert{},
		},
	}

	a := newTestAnalyzer(&clientTest.MockReader{}, 0, 10)

	for _, test := range tests {
		a.Now = fakeNow(test.t)
		got := a.MasterAlerts(&messages.MasterLocation{URL: *urlParse("https://build.chromium.org/p/"+test.master, t)}, &test.be)
		if !reflect.DeepEqual(got, test.want) {
			t.Errorf("%s failed. Got %+v, want: %+v\nDiff: %v", test.name, got, test.want,
				ansidiff.Diff(got, test.want))
		}
	}
}

func TestBuilderAlerts(t *testing.T) {
	tests := []struct {
		name         string
		url          string
		be           messages.BuildExtract
		filter       string
		t            time.Time
		wantBuilders []messages.Alert
		wantMasters  []messages.Alert
	}{
		{
			name:         "Empty",
			url:          "https://build.chromium.org/p/fake.master/json",
			wantBuilders: []messages.Alert{},
			wantMasters:  []messages.Alert{},
		},
		{
			name: "No Alerts",
			url:  "https://build.chromium.org/p/fake.master/json",
			be: messages.BuildExtract{
				CreatedTimestamp: messages.EpochTime(100),
			},
			t:            time.Unix(100, 0),
			wantBuilders: []messages.Alert{},
			wantMasters:  []messages.Alert{},
		},
	}

	a := newTestAnalyzer(&clientTest.MockReader{}, 0, 10)

	for _, test := range tests {
		a.Now = fakeNow(test.t)
		got := a.BuilderAlerts("tree", &messages.MasterLocation{URL: *urlParse(test.url, t)}, &test.be)
		if !reflect.DeepEqual(got, test.wantBuilders) {
			t.Errorf("%s failed. Got %+v, want: %+v", test.name, got, test.wantBuilders)
		}
	}
}

func TestLittleBBuilderAlerts(t *testing.T) {
	tests := []struct {
		name       string
		master     string
		builder    string
		b          messages.Builder
		builds     map[string]*messages.Build
		time       time.Time
		wantAlerts []messages.Alert
		wantErrs   []error
	}{
		{
			name:     "empty",
			wantErrs: []error{errNoRecentBuilds},
		},
		{
			name:    "builders ok",
			master:  "fake.master",
			builder: "fake.builder",
			builds: analyzertest.NewBuilderFaker("fake.master", "fake.builder").
				Build(0).Times(10, 100).
				Step("fake_step").Times(10, 100).BuilderFaker.Builds,
			b: messages.Builder{
				State:        messages.StateBuilding,
				BuilderName:  "fake.builder",
				CachedBuilds: []int64{0},
			},
			wantAlerts: []messages.Alert{},
			wantErrs:   []error{},
		},
		{
			name:    "builder building for too long",
			master:  "fake.master",
			builder: "hung.builder",
			builds: analyzertest.NewBuilderFaker("fake.master", "hung.builder").
				Build(0).Times(10, 100).
				Step("fake_step").Times(10, 100).BuilderFaker.
				Build(1).Times(100, 0).
				Step("fake_step").Times(100, 0).BuilderFaker.Builds,
			b: messages.Builder{
				State:        messages.StateBuilding,
				BuilderName:  "fake.builder",
				CachedBuilds: []int64{0, 1},
			},
			time: time.Unix(0, 0).Add(4 * time.Hour),
			wantAlerts: []messages.Alert{
				{
					Key:       "fake.master.hung.builder.hung",
					Title:     "fake.master.hung.builder is hung in step fake_step.",
					Type:      messages.AlertHungBuilder,
					StartTime: 100,
					Time:      messages.TimeToEpochTime(time.Unix(0, 0).Add(4 * time.Hour)),
					Body:      "fake.master.hung.builder has been building for 3h58m20s (last step update 1970-01-01 00:01:40 +0000 UTC), past the alerting threshold of 3h0m0s",
					Severity:  hungBuilderSev,
					Links: []messages.Link{
						{Title: "Builder", Href: urlParse("https://build.chromium.org/p/fake.master/builders/hung.builder", t).String()},
						{Title: "Last build", Href: urlParse("https://build.chromium.org/p/fake.master/builders/hung.builder/builds/1", t).String()},
						{Title: "Last build step", Href: urlParse("https://build.chromium.org/p/fake.master/builders/hung.builder/builds/1/steps/fake_step", t).String()},
					},
				},
			},
			wantErrs: []error{},
		},
	}

	a := newTestAnalyzer(nil, 0, 10)

	for _, test := range tests {
		a.Now = fakeNow(test.time)
		a.Reader = clientTest.MockReader{
			Builds: test.builds,
		}
		fmt.Printf("test %s", test.name)
		gotAlerts, gotErrs := a.builderAlerts("tree", &messages.MasterLocation{URL: *urlParse("https://build.chromium.org/p/"+test.master, t)}, test.builder, &test.b)
		if !reflect.DeepEqual(gotAlerts, test.wantAlerts) {
			t.Errorf("%s failed. Got:\n%+v, want:\n%+v\nDiff: %v", test.name, gotAlerts, test.wantAlerts,
				ansidiff.Diff(gotAlerts, test.wantAlerts))
		}
		if !reflect.DeepEqual(gotErrs, test.wantErrs) {
			t.Errorf("%s failed. Got %+v, want: %+v", test.name, gotErrs, test.wantErrs)
		}
	}
}

func TestBuilderStepAlerts(t *testing.T) {
	t.Parallel()

	Convey("test BuilderStepAlerts", t, func() {
		tests := []struct {
			name         string
			master       string
			builder      string
			recentBuilds []int64
			builds       map[string]*messages.Build
			finditData   []*messages.FinditResult
			time         time.Time
			wantAlerts   []messages.Alert
			wantErrs     []error
		}{
			{
				name: "empty",
			},
			{
				name:         "builders ok",
				master:       "fake.master",
				builder:      "fake.builder",
				recentBuilds: []int64{0},
				builds: analyzertest.NewBuilderFaker("fake.master", "fake.builder").
					Build(0).Times(0, 1).Step("fake_step").Results(0).BuilderFaker.Builds,
			},
			{
				name:         "one build failure",
				master:       "fake.master",
				builder:      "fake.builder",
				recentBuilds: []int64{0},
				builds: analyzertest.NewBuilderFaker("fake.master", "fake.builder").
					Build(0).Times(0, 1).GotRevision("refs/heads/master@{#291569}").
					Step("fake_step").Results(2).BuilderFaker.Builds,
				wantAlerts: []messages.Alert{
					{
						Key:      "fake.master.fake.builder.fake_step.",
						Title:    "fakeTitle",
						Type:     messages.AlertBuildFailure,
						Body:     "",
						Severity: newFailureSev,
						Extension: messages.BuildFailure{
							Builders: []messages.AlertedBuilder{
								{
									Name: "fake.builder",
									URL:  urlParse("https://build.chromium.org/p/fake.master/builders/fake.builder", t).String(),
								},
							},
							RegressionRanges: []messages.RegressionRange{
								{
									Repo:      "chromium",
									Positions: []string{"refs/heads/master@{#291569}"},
								},
							},
							StepAtFault: &messages.BuildStep{
								Master: &messages.MasterLocation{URL: *urlParse("https://build.chromium.org/p/fake.master", t)},
								Build: &messages.Build{
									BuilderName: "fake.builder",
									Number:      0,
									Times:       []messages.EpochTime{0, 1},
									Steps: []messages.Step{
										{
											Name:       "fake_step",
											IsFinished: true,
											Results:    []interface{}{float64(2)},
										},
									},
									Properties: [][]interface{}{
										{"got_revision_cp", "refs/heads/master@{#291569}"},
									},
								},
								Step: &messages.Step{
									Name:       "fake_step",
									IsFinished: true,
									Results:    []interface{}{float64(2)},
								},
							},
							Reason: &messages.Reason{
								Raw: &fakeReasonRaw{},
							},
						},
					},
				},
			},
			{
				name:         "one build failure with findit",
				master:       "fake.master",
				builder:      "fake.builder",
				recentBuilds: []int64{0},
				builds: analyzertest.NewBuilderFaker("fake.master", "fake.builder").
					Build(0).Times(0, 1).GotRevision("refs/heads/master@{#291569}").
					Step("fake_step").Results(2).BuilderFaker.Builds,
				finditData: []*messages.FinditResult{
					{
						SuspectedCLs: []messages.SuspectCL{
							{
								RepoName:       "repo",
								Revision:       "deadbeef",
								CommitPosition: 1234,
							},
						},
					},
				},
				wantAlerts: []messages.Alert{
					{
						Key:      "fake.master.fake.builder.fake_step.",
						Title:    "fakeTitle",
						Type:     messages.AlertBuildFailure,
						Body:     "",
						Severity: newFailureSev,
						Extension: messages.BuildFailure{
							Builders: []messages.AlertedBuilder{
								{
									Name: "fake.builder",
									URL:  urlParse("https://build.chromium.org/p/fake.master/builders/fake.builder", t).String(),
								},
							},
							StepAtFault: &messages.BuildStep{
								Master: &messages.MasterLocation{URL: *urlParse("https://build.chromium.org/p/fake.master", t)},
								Build: &messages.Build{
									BuilderName: "fake.builder",
									Number:      0,
									Times:       []messages.EpochTime{0, 1},
									Steps: []messages.Step{
										{
											Name:       "fake_step",
											IsFinished: true,
											Results:    []interface{}{float64(2)},
										},
									},
									Properties: [][]interface{}{
										{"got_revision_cp", "refs/heads/master@{#291569}"},
									},
								},
								Step: &messages.Step{
									Name:       "fake_step",
									IsFinished: true,
									Results:    []interface{}{float64(2)},
								},
							},
							Reason: &messages.Reason{
								Raw: &fakeReasonRaw{},
							},
							RegressionRanges: []messages.RegressionRange{
								{
									Repo:      "chromium",
									Positions: []string{"refs/heads/master@{#291569}"},
								},
							},
							SuspectedCLs: []messages.SuspectCL{
								{
									RepoName:       "repo",
									Revision:       "deadbeef",
									CommitPosition: 1234,
								},
							},
						},
					},
				},
			},
			{
				name:         "repeated build failure",
				master:       "fake.master",
				builder:      "fake.builder",
				recentBuilds: []int64{0, 1, 2, 3},
				builds: analyzertest.NewBuilderFaker("fake.master", "fake.builder").
					Build(0).Times(0, 1).GotRevision("refs/heads/master@{#291569}").
					Step("fake_step").Results(2).BuilderFaker.
					Build(1).Times(2, 3).GotRevision("refs/heads/master@{#291570}").
					Step("fake_step").Results(2).BuilderFaker.
					Build(2).Times(4, 5).GotRevision("refs/heads/master@{#291570}").
					Step("fake_step").Results(2).BuilderFaker.
					Build(3).Times(6, 7).GotRevision("refs/heads/master@{#291570}").
					Step("fake_step").Results(2).BuilderFaker.Builds,
				wantAlerts: []messages.Alert{
					{
						Key:      "fake.master.fake.builder.fake_step.",
						Title:    "fakeTitle",
						Type:     messages.AlertBuildFailure,
						Body:     "",
						Severity: reliableFailureSev,
						Time:     6,
						Extension: messages.BuildFailure{
							Builders: []messages.AlertedBuilder{
								{
									Name:          "fake.builder",
									URL:           urlParse("https://build.chromium.org/p/fake.master/builders/fake.builder", t).String(),
									FirstFailure:  0,
									LatestFailure: 3,
								},
							},
							StepAtFault: &messages.BuildStep{
								Master: &messages.MasterLocation{URL: *urlParse("https://build.chromium.org/p/fake.master", t)},
								Build: &messages.Build{
									BuilderName: "fake.builder",
									Number:      3,
									Times:       []messages.EpochTime{6, 7},
									Steps: []messages.Step{
										{
											Name:       "fake_step",
											IsFinished: true,
											Results:    []interface{}{float64(2)},
										},
									},
									Properties: [][]interface{}{
										{"got_revision_cp", "refs/heads/master@{#291570}"},
									},
								},
								Step: &messages.Step{
									Name:       "fake_step",
									IsFinished: true,
									Results:    []interface{}{float64(2)},
								},
							},
							Reason: &messages.Reason{
								Raw: &fakeReasonRaw{},
							},
							RegressionRanges: []messages.RegressionRange{
								{
									Repo: "chromium",
									Positions: []string{
										"refs/heads/master@{#291569}",
									},
								},
							},
						},
					},
				},
			},
			{
				name:         "new double failures counted",
				master:       "fake.master",
				builder:      "fake.builder",
				recentBuilds: []int64{0, 1, 2},
				builds: analyzertest.NewBuilderFaker("fake.master", "fake.builder").
					Build(0).Times(0, 1).GotRevision("refs/heads/master@{#291569}").
					Step("fake_step").Results(2).BuilderFaker.
					Build(1).Times(2, 3).GotRevision("refs/heads/master@{#291570}").
					Step("fake_step").Results(2).BuilderFaker.
					Build(2).Times(4, 5).GotRevision("refs/heads/master@{#291570}").
					Step("fake_step").Results(2).BuildFaker.
					Step("other_step").Results(2).BuilderFaker.Builds,
				wantAlerts: []messages.Alert{
					{
						Key:       "fake.master.fake.builder.other_step.",
						Title:     "fakeTitle",
						Type:      messages.AlertBuildFailure,
						Body:      "",
						Time:      4,
						StartTime: 4,
						Severity:  newFailureSev,
						Extension: messages.BuildFailure{
							Builders: []messages.AlertedBuilder{
								{
									Name:          "fake.builder",
									URL:           urlParse("https://build.chromium.org/p/fake.master/builders/fake.builder", t).String(),
									FirstFailure:  2,
									LatestFailure: 2,
									StartTime:     4,
								},
							},
							StepAtFault: &messages.BuildStep{
								Master: &messages.MasterLocation{URL: *urlParse("https://build.chromium.org/p/fake.master", t)},
								Build: &messages.Build{
									BuilderName: "fake.builder",
									Number:      2,
									Times:       []messages.EpochTime{4, 5},
									Steps: []messages.Step{
										{
											Name:       "fake_step",
											IsFinished: true,
											Results:    []interface{}{float64(2)},
										},
										{
											Name:       "other_step",
											IsFinished: true,
											Results:    []interface{}{float64(2)},
										},
									},
									Properties: [][]interface{}{
										{"got_revision_cp", "refs/heads/master@{#291570}"},
									},
								},
								Step: &messages.Step{
									Name:       "other_step",
									IsFinished: true,
									Results:    []interface{}{float64(2)},
								},
							},
							Reason: &messages.Reason{
								Raw: &fakeReasonRaw{},
							},
							RegressionRanges: []messages.RegressionRange{
								{
									Repo: "chromium",
									Positions: []string{
										"refs/heads/master@{#291570}",
									},
								},
							},
						},
					},
					{
						Key:       "fake.master.fake.builder.fake_step.",
						Title:     "fakeTitle",
						Type:      messages.AlertBuildFailure,
						Body:      "",
						Severity:  reliableFailureSev,
						Time:      4,
						StartTime: 0,
						Extension: messages.BuildFailure{
							Builders: []messages.AlertedBuilder{
								{
									Name:          "fake.builder",
									URL:           urlParse("https://build.chromium.org/p/fake.master/builders/fake.builder", t).String(),
									FirstFailure:  0,
									LatestFailure: 2,
								},
							},
							StepAtFault: &messages.BuildStep{
								Master: &messages.MasterLocation{URL: *urlParse("https://build.chromium.org/p/fake.master", t)},
								Build: &messages.Build{
									BuilderName: "fake.builder",
									Number:      2,
									Times:       []messages.EpochTime{4, 5},
									Steps: []messages.Step{
										{
											Name:       "fake_step",
											IsFinished: true,
											Results:    []interface{}{float64(2)},
										},
										{
											Name:       "other_step",
											IsFinished: true,
											Results:    []interface{}{float64(2)},
										},
									},
									Properties: [][]interface{}{
										{"got_revision_cp", "refs/heads/master@{#291570}"},
									},
								},
								Step: &messages.Step{
									Name:       "fake_step",
									IsFinished: true,
									Results:    []interface{}{float64(2)},
								},
							},
							Reason: &messages.Reason{
								Raw: &fakeReasonRaw{},
							},
							RegressionRanges: []messages.RegressionRange{
								{
									Repo: "chromium",
									Positions: []string{
										"refs/heads/master@{#291569}",
									},
								},
							},
						},
					},
				},
			},
			{
				name:         "old failures not counted",
				master:       "fake.master",
				builder:      "fake.builder",
				recentBuilds: []int64{0, 1, 2},
				builds: analyzertest.NewBuilderFaker("fake.master", "fake.builder").
					Build(0).Times(0, 1).GotRevision("refs/heads/master@{#291569}").
					Step("fake_step").Results(2).BuildFaker.
					Step("other_step").Results(2).BuilderFaker.
					Build(1).Times(2, 3).GotRevision("refs/heads/master@{#291570}").
					Step("fake_step").Results(2).BuilderFaker.
					Build(2).Times(4, 5).GotRevision("refs/heads/master@{#291570}").
					Step("fake_step").Results(2).BuilderFaker.Builds,
				wantAlerts: []messages.Alert{
					{
						Key:      "fake.master.fake.builder.fake_step.",
						Title:    "fakeTitle",
						Type:     messages.AlertBuildFailure,
						Body:     "",
						Severity: reliableFailureSev,
						Time:     4,
						Extension: messages.BuildFailure{
							Builders: []messages.AlertedBuilder{
								{
									Name:          "fake.builder",
									URL:           urlParse("https://build.chromium.org/p/fake.master/builders/fake.builder", t).String(),
									FirstFailure:  0,
									LatestFailure: 2,
								},
							},
							StepAtFault: &messages.BuildStep{
								Master: &messages.MasterLocation{URL: *urlParse("https://build.chromium.org/p/fake.master", t)},
								Build: &messages.Build{
									BuilderName: "fake.builder",
									Number:      2,
									Times:       []messages.EpochTime{4, 5},
									Steps: []messages.Step{
										{
											Name:       "fake_step",
											IsFinished: true,
											Results:    []interface{}{float64(2)},
										},
									},
									Properties: [][]interface{}{
										{"got_revision_cp", "refs/heads/master@{#291570}"},
									},
								},
								Step: &messages.Step{
									Name:       "fake_step",
									IsFinished: true,
									Results:    []interface{}{float64(2)},
								},
							},
							Reason: &messages.Reason{
								Raw: &fakeReasonRaw{},
							},
							RegressionRanges: []messages.RegressionRange{
								{
									Repo: "chromium",
									Positions: []string{
										"refs/heads/master@{#291569}",
									},
								},
							},
						},
					},
				},
			},
		}

		a := newTestAnalyzer(nil, 0, 10)

		for _, test := range tests {
			test := test
			Convey(test.name, func() {
				a.Now = fakeNow(time.Unix(0, 0))
				a.Reader = clientTest.MockReader{
					Builds:        test.builds,
					FinditResults: test.finditData,
				}

				gotAlerts, gotErrs := a.builderStepAlerts("tree", &messages.MasterLocation{URL: *urlParse("https://build.chromium.org/p/"+test.master, t)}, test.builder, test.recentBuilds)

				sort.Sort(sortAlerts(gotAlerts))
				sort.Sort(sortAlerts(test.wantAlerts))

				So(gotAlerts, ShouldResemble, test.wantAlerts)
				if !reflect.DeepEqual(gotErrs, test.wantErrs) {
					t.Errorf("%s failed. Got %+v, want: %+v", test.name, gotErrs, test.wantErrs)
				}
			})
		}
	})
}

type sortAlerts []messages.Alert

func (a sortAlerts) Len() int           { return len(a) }
func (a sortAlerts) Swap(i, j int)      { a[i], a[j] = a[j], a[i] }
func (a sortAlerts) Less(i, j int) bool { return a[i].Key > a[j].Key }

func TestMergeAlertsByReason(t *testing.T) {
	Convey("test MergeAlertsByReason", t, func() {
		tests := []struct {
			name     string
			in, want []messages.Alert
		}{
			{
				name: "empty",
				want: []messages.Alert{},
			},
			{
				name: "no merges",
				in: []messages.Alert{
					{
						Type: messages.AlertBuildFailure,
						Extension: messages.BuildFailure{
							Builders: []messages.AlertedBuilder{
								{Name: "builder A"},
							},
							Reason: &messages.Reason{
								Raw: &fakeReasonRaw{
									"reason_a",
								},
							},
							RegressionRanges: []messages.RegressionRange{
								{
									Repo: "repo.a",
								},
							},
						},
					},
					{
						Type: messages.AlertBuildFailure,
						Extension: messages.BuildFailure{
							Builders: []messages.AlertedBuilder{
								{Name: "builder B"},
							},
							Reason: &messages.Reason{
								Raw: &fakeReasonRaw{
									"reason_b",
								},
							},
							RegressionRanges: []messages.RegressionRange{
								{
									Repo: "repo.b",
								},
							},
						},
					},
				},
				want: []messages.Alert{
					{
						Type: messages.AlertBuildFailure,
						Extension: messages.BuildFailure{
							Builders: []messages.AlertedBuilder{
								{Name: "builder A"},
							},
							Reason: &messages.Reason{
								Raw: &fakeReasonRaw{
									"reason_a",
								},
							},
							RegressionRanges: []messages.RegressionRange{
								{
									Repo: "repo.a",
								},
							},
						},
					},
					{
						Type: messages.AlertBuildFailure,
						Extension: messages.BuildFailure{
							Builders: []messages.AlertedBuilder{
								{Name: "builder B"},
							},
							Reason: &messages.Reason{
								Raw: &fakeReasonRaw{
									"reason_b",
								},
							},
							RegressionRanges: []messages.RegressionRange{
								{
									Repo: "repo.b",
								},
							},
						},
					},
				},
			},
			{
				name: "multiple builders fail on step_a",
				in: []messages.Alert{
					{
						Type: messages.AlertBuildFailure,
						Extension: messages.BuildFailure{
							Builders: []messages.AlertedBuilder{
								{Name: "builder A"},
							},
							Reason: &messages.Reason{
								Raw: &fakeReasonRaw{},
							},
							RegressionRanges: []messages.RegressionRange{
								{
									Repo: "repo.a",
								},
							},
						},
					},
					{
						Type: messages.AlertBuildFailure,
						Extension: messages.BuildFailure{
							Builders: []messages.AlertedBuilder{
								{Name: "builder B"},
							},
							Reason: &messages.Reason{
								Raw: &fakeReasonRaw{},
							},
							RegressionRanges: []messages.RegressionRange{
								{
									Repo: "repo.b",
								},
							},
						},
					},
					{
						Type: messages.AlertBuildFailure,
						Extension: messages.BuildFailure{
							Builders: []messages.AlertedBuilder{
								{Name: "builder C"},
							},
							Reason: &messages.Reason{
								Raw: &fakeReasonRaw{},
							},
							RegressionRanges: []messages.RegressionRange{
								{
									Repo: "repo.c",
								},
							},
						},
					},
				},
				want: []messages.Alert{
					{
						Title: "fakeTitle",
						Type:  messages.AlertBuildFailure,
						Body:  "builder A, builder B, builder C",
						Extension: messages.BuildFailure{
							Builders: []messages.AlertedBuilder{
								{Name: "builder A"},
								{Name: "builder B"},
								{Name: "builder C"},
							},
							Reason: &messages.Reason{
								Raw: &fakeReasonRaw{},
							},
							RegressionRanges: []messages.RegressionRange{
								{
									Repo:      "repo.a",
									Positions: []string{},
								},
								{
									Repo:      "repo.b",
									Positions: []string{},
								},
								{
									Repo:      "repo.c",
									Positions: []string{},
								},
							},
						},
					},
				},
			},
			{
				name: "multiple builders fail on step_a with tests",
				in: []messages.Alert{
					{
						Type: messages.AlertBuildFailure,
						Extension: messages.BuildFailure{
							Builders: []messages.AlertedBuilder{
								{Name: "builder A"},
							},
							Reason: &messages.Reason{
								Raw: &fakeReasonRaw{},
							},
						},
					},
					{
						Type: messages.AlertBuildFailure,
						Extension: messages.BuildFailure{
							Builders: []messages.AlertedBuilder{
								{Name: "builder B"},
							},
							Reason: &messages.Reason{
								Raw: &fakeReasonRaw{},
							},
						},
					},
				},
				want: []messages.Alert{
					{
						Title: "fakeTitle",
						Type:  messages.AlertBuildFailure,
						Body:  "builder A, builder B",
						Extension: messages.BuildFailure{
							Builders: []messages.AlertedBuilder{
								{Name: "builder A"},
								{Name: "builder B"},
							},
							Reason: &messages.Reason{
								Raw: &fakeReasonRaw{},
							},
							RegressionRanges: []messages.RegressionRange{},
						},
					},
				},
			},
		}

		a := newTestAnalyzer(&clientTest.MockReader{}, 0, 10)
		for _, test := range tests {
			test := test
			Convey(test.name, func() {
				got := a.mergeAlertsByReason(test.in)
				So(got, ShouldResemble, test.want)
			})
		}
	})
}

func TestStepFailures(t *testing.T) {
	t.Parallel()

	Convey("test StepFailures", t, func() {
		tests := []struct {
			name            string
			master, builder string
			b               *messages.Build
			buildNum        int64
			bCache          map[string]*messages.Build
			want            []*messages.BuildStep
			wantErr         error
		}{
			{
				name:    "empty",
				master:  "fake.master",
				builder: "fake.builder",
			},
			{
				name:     "breaking step",
				master:   "stepCheck.master",
				builder:  "fake.builder",
				buildNum: 0,
				bCache: analyzertest.NewBuilderFaker("stepCheck.master", "fake.builder").
					Build(0).Step("ok_step").Results(0).BuildFaker.
					Step("broken_step").Results(3).BuilderFaker.Builds,
				want: []*messages.BuildStep{
					{
						Master: &messages.MasterLocation{URL: *urlParse("https://build.chromium.org/p/stepCheck.master", t)},
						Build: &messages.Build{
							BuilderName: "fake.builder",
							Steps: []messages.Step{
								{
									Name:       "ok_step",
									IsFinished: true,
									Results:    []interface{}{float64(0)},
								},
								{
									Name:       "broken_step",
									IsFinished: true,
									Results:    []interface{}{float64(3)},
								},
							},
						},
						Step: &messages.Step{
							Name:       "broken_step",
							IsFinished: true,
							Results:    []interface{}{float64(3)},
						},
					},
				},
			},
		}

		mc := &clientTest.MockReader{}
		a := newTestAnalyzer(mc, 0, 10)

		for _, test := range tests {
			test := test
			Convey(test.name, func() {
				mc.BuildValue = test.b
				mc.BCache = test.bCache
				got, err := a.stepFailures(&messages.MasterLocation{URL: *urlParse("https://build.chromium.org/p/"+test.master, t)}, test.builder, test.buildNum)
				So(got, ShouldResemble, test.want)
				So(err, ShouldResemble, test.wantErr)
			})
		}
	})
}

func TestStepFailureAlerts(t *testing.T) {
	t.Parallel()

	Convey("test StepFailureAlerts", t, func() {
		tests := []struct {
			name        string
			failures    []*messages.BuildStep
			testResults messages.TestResults
			alerts      []messages.Alert
			err         error
		}{
			{
				name:   "empty",
				alerts: []messages.Alert{},
			},
			{
				name: "single failure",
				failures: []*messages.BuildStep{
					{
						Master: &messages.MasterLocation{URL: *urlParse("https://build.chromium.org/p/fake.master", t)},
						Build: &messages.Build{
							BuilderName: "fake.builder",
							Number:      2,
							Times:       []messages.EpochTime{0, 1},
						},
						Step: &messages.Step{
							Name: "steps",
						},
					},
					{
						Master: &messages.MasterLocation{URL: *urlParse("https://build.chromium.org/p/fake.master", t)},
						Build: &messages.Build{
							BuilderName: "fake.builder",
							Number:      42,
							Times:       []messages.EpochTime{0, 1},
						},
						Step: &messages.Step{
							Name: "fake_tests",
						},
					},
				},
				testResults: messages.TestResults{},
				alerts: []messages.Alert{
					{
						Key:      "fake.master.fake.builder.fake_tests.",
						Title:    "fakeTitle",
						Body:     "",
						Severity: newFailureSev,
						Type:     messages.AlertBuildFailure,
						Extension: messages.BuildFailure{
							Builders: []messages.AlertedBuilder{
								{
									Name:          "fake.builder",
									URL:           urlParse("https://build.chromium.org/p/fake.master/builders/fake.builder", t).String(),
									FirstFailure:  42,
									LatestFailure: 42,
								},
							},
							Reason: &messages.Reason{
								Raw: &fakeReasonRaw{},
							},
							StepAtFault: &messages.BuildStep{
								Master: &messages.MasterLocation{URL: *urlParse("https://build.chromium.org/p/fake.master", t)},
								Build: &messages.Build{
									BuilderName: "fake.builder",
									Number:      42,
									Times:       []messages.EpochTime{0, 1},
								},
								Step: &messages.Step{
									Name: "fake_tests",
								},
							},
							RegressionRanges: []messages.RegressionRange{},
						},
					},
				},
			},
		}

		mc := &clientTest.MockReader{}
		a := newTestAnalyzer(mc, 0, 10)
		a.Now = fakeNow(time.Unix(0, 0))

		for _, test := range tests {
			test := test
			Convey(test.name, func() {
				mc.TestResultsValue = &test.testResults
				alerts, err := a.stepFailureAlerts("tree", test.failures)
				So(alerts, ShouldResemble, test.alerts)
				So(err, ShouldResemble, test.err)
			})
		}
	})
}

func TestLatestBuildStep(t *testing.T) {
	tests := []struct {
		name       string
		b          messages.Build
		wantStep   string
		wantUpdate messages.EpochTime
		wantErr    error
	}{
		{
			name:    "blank",
			wantErr: errNoBuildSteps,
		},
		{
			name: "done time is latest",
			b: messages.Build{
				Times: []messages.EpochTime{0},
				Steps: []messages.Step{
					{
						Name: "done step",
						Times: []messages.EpochTime{
							messages.TimeToEpochTime(time.Unix(6, 0)),
							messages.TimeToEpochTime(time.Unix(42, 0)),
						},
					},
				},
			},
			wantStep:   "done step",
			wantUpdate: messages.TimeToEpochTime(time.Unix(42, 0)),
		},
		{
			name: "started time is latest",
			b: messages.Build{
				Times: []messages.EpochTime{0},
				Steps: []messages.Step{
					{
						Name: "start step",
						Times: []messages.EpochTime{
							messages.TimeToEpochTime(time.Unix(42, 0)),
						},
					},
				},
			},
			wantStep:   "start step",
			wantUpdate: messages.TimeToEpochTime(time.Unix(42, 0)),
		},
		{
			name: "started time is latest, multiple steps",
			b: messages.Build{
				Times: []messages.EpochTime{0},
				Steps: []messages.Step{
					{
						Name: "start step",
						Times: []messages.EpochTime{
							messages.TimeToEpochTime(time.Unix(6, 0)),
							messages.TimeToEpochTime(time.Unix(7, 0)),
						},
					},
					{
						Name: "second step",
						Times: []messages.EpochTime{
							messages.TimeToEpochTime(time.Unix(42, 0)),
							messages.TimeToEpochTime(time.Unix(0, 0)),
						},
					},
				},
			},
			wantStep:   "second step",
			wantUpdate: messages.TimeToEpochTime(time.Unix(42, 0)),
		},
		{
			name: "done time is latest, multiple steps",
			b: messages.Build{
				Times: []messages.EpochTime{0},
				Steps: []messages.Step{
					{
						Name: "start step",
						Times: []messages.EpochTime{
							messages.TimeToEpochTime(time.Unix(0, 0)),
							messages.TimeToEpochTime(time.Unix(6, 0)),
						},
					},
					{
						Name: "second step",
						Times: []messages.EpochTime{
							messages.TimeToEpochTime(time.Unix(7, 0)),
							messages.TimeToEpochTime(time.Unix(42, 0)),
						},
					},
				},
			},
			wantStep:   "second step",
			wantUpdate: messages.TimeToEpochTime(time.Unix(42, 0)),
		},
		{
			name: "build is done",
			b: messages.Build{
				Times: []messages.EpochTime{
					messages.TimeToEpochTime(time.Unix(0, 0)),
					messages.TimeToEpochTime(time.Unix(42, 0)),
				},
				Steps: []messages.Step{
					{
						Name: "start step",
						Times: []messages.EpochTime{
							messages.TimeToEpochTime(time.Unix(0, 0)),
							messages.TimeToEpochTime(time.Unix(0, 0)),
						},
					},
					{
						Name: "second step",
						Times: []messages.EpochTime{
							messages.TimeToEpochTime(time.Unix(6, 0)),
							messages.TimeToEpochTime(time.Unix(7, 0)),
						},
					},
				},
			},
			wantStep:   StepCompletedRun,
			wantUpdate: messages.TimeToEpochTime(time.Unix(42, 0)),
		},
	}

	a := newTestAnalyzer(&clientTest.MockReader{}, 0, 10)
	a.Now = fakeNow(time.Unix(0, 0))
	for _, test := range tests {
		gotStep, gotUpdate, gotErr := a.latestBuildStep(&test.b)
		if gotStep != test.wantStep {
			t.Errorf("%s failed. Got %q, want %q.", test.name, gotStep, test.wantStep)
		}
		if gotUpdate != test.wantUpdate {
			t.Errorf("%s failed. Got %v, want %v.", test.name, gotUpdate, test.wantUpdate)
		}
		if gotErr != test.wantErr {
			t.Errorf("%s failed. Got %s, want %s.", test.name, gotErr, test.wantErr)
		}
	}
}

func TestExcludeFailure(t *testing.T) {
	tests := []struct {
		name                        string
		gk                          messages.GatekeeperConfig
		gkt                         map[string][]messages.TreeMasterConfig
		master, builder, step, tree string
		want                        bool
	}{
		{
			name:    "empty config",
			tree:    "test_tree1",
			master:  "fake.master",
			builder: "fake.builder",
			step:    "fake_step",
			want:    false,
		},
		{
			name:    "specifically excluded builder",
			tree:    "test_tree2",
			master:  "fake.master",
			builder: "fake.builder",
			step:    "fake_step",
			gk: messages.GatekeeperConfig{Masters: map[string][]messages.MasterConfig{
				"https://build.chromium.org/p/fake.master": {{
					ExcludedBuilders: []string{"fake.builder"},
				}},
			}},
			want: true,
		},
		{
			name:    "specifically excluded master step",
			tree:    "test_tree3",
			master:  "fake.master",
			builder: "fake.builder",
			step:    "fake_step",
			gk: messages.GatekeeperConfig{Masters: map[string][]messages.MasterConfig{
				"https://build.chromium.org/p/fake.master": {{
					ExcludedSteps: []string{"fake_step"},
				}},
			}},
			want: true,
		},
		{
			name:    "specifically excluded builder step",
			tree:    "test_tree4",
			master:  "fake.master",
			builder: "fake.builder",
			step:    "fake_step",
			gk: messages.GatekeeperConfig{Masters: map[string][]messages.MasterConfig{
				"https://build.chromium.org/p/fake.master": {{
					Builders: map[string]messages.BuilderConfig{
						"fake.builder": {
							ExcludedSteps: []string{"fake_step"},
						},
					}},
				}},
			},
			want: true,
		},
		{
			name:    "wildcard builder excluded",
			tree:    "test_tree5",
			master:  "fake.master",
			builder: "fake.builder",
			step:    "fake_step",
			gk: messages.GatekeeperConfig{Masters: map[string][]messages.MasterConfig{
				"https://build.chromium.org/p/fake.master": {{
					ExcludedBuilders: []string{"*"},
				}},
			}},
			want: true,
		},
		{
			name:    "config should exclude builder (tree config)",
			tree:    "test_tree6",
			master:  "fake.master",
			builder: "fake.builder",
			step:    "fake_step",
			gk: messages.GatekeeperConfig{Masters: map[string][]messages.MasterConfig{
				"https://build.chromium.org/p/fake.master": {{
					Builders: map[string]messages.BuilderConfig{
						"*": {},
					},
				}},
			}},
			gkt: map[string][]messages.TreeMasterConfig{
				"test_tree": {
					messages.TreeMasterConfig{
						Masters: map[messages.MasterLocation][]string{
							messages.MasterLocation{URL: *urlParse(
								"https://build.chromium.org/p/fake.master", t)}: {"other.builder"},
						},
					},
				},
			},
			want: true,
		},
		{
			name:    "config shouldn't exclude builder (tree config)",
			tree:    "test_tree7",
			master:  "fake.master",
			builder: "fake.builder",
			step:    "fake_step",
			gk: messages.GatekeeperConfig{Masters: map[string][]messages.MasterConfig{
				"https://build.chromium.org/p/fake.master": {{
					Builders: map[string]messages.BuilderConfig{
						"*": {},
					},
				}},
			}},
			gkt: map[string][]messages.TreeMasterConfig{
				"test_tree7": {
					messages.TreeMasterConfig{
						Masters: map[messages.MasterLocation][]string{
							messages.MasterLocation{URL: *urlParse(
								"https://build.chromium.org/p/fake.master", t)}: {"fake.builder"},
						},
					},
				},
			},
			want: false,
		},
		{
			name:    "config shouldn't exclude builder (tree config glob)",
			tree:    "test_tree8",
			master:  "fake.master",
			builder: "fake.builder",
			step:    "fake_step",
			gk: messages.GatekeeperConfig{Masters: map[string][]messages.MasterConfig{
				"https://build.chromium.org/p/fake.master": {{
					Builders: map[string]messages.BuilderConfig{
						"*": {},
					},
				}},
			}},
			gkt: map[string][]messages.TreeMasterConfig{
				"test_tree8": {
					messages.TreeMasterConfig{
						Masters: map[messages.MasterLocation][]string{
							messages.MasterLocation{URL: *urlParse(
								"https://build.chromium.org/p/fake.master", t)}: {"*"},
						},
					},
				},
			},
			want: false,
		},
	}

	a := newTestAnalyzer(&clientTest.MockReader{}, 0, 10)
	for _, test := range tests {
		a.Gatekeeper = NewGatekeeperRules([]*messages.GatekeeperConfig{&test.gk}, test.gkt)
		got := a.Gatekeeper.ExcludeFailure(test.tree, &messages.MasterLocation{URL: *urlParse("https://build.chromium.org/p/"+test.master, t)}, test.builder, test.step)
		if got != test.want {
			t.Errorf("%s failed. Got: %+v, want: %+v", test.name, got, test.want)
		}
	}
}
