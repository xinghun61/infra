// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package analyzer

import (
	"fmt"
	"infra/libs/testing/ansidiff"
	"infra/monitoring/client"
	"infra/monitoring/messages"
	"reflect"
	"testing"
	"time"
)

func fakeNow(t time.Time) func() time.Time {
	return func() time.Time {
		return t
	}
}

type mockReader struct {
	bCache       map[string]*messages.Build
	build        *messages.Build
	builds       map[string]*messages.Build
	latestBuilds map[string]map[string][]*messages.Build
	testResults  *messages.TestResults
	stdioForStep []string
	buildFetchError,
	stepFetchError,
	stdioForStepError error
	buildFetchErrs map[string]error
}

func (m mockReader) Build(master, builder string, buildNum int64) (*messages.Build, error) {
	if m.build != nil {
		return m.build, m.buildFetchError
	}

	key := fmt.Sprintf("%s/%s/%d", master, builder, buildNum)
	if b, ok := m.bCache[key]; ok {
		return b, nil
	}
	fmt.Printf("looking up %q: %+v\n", key, m.builds[key])
	return m.builds[key], m.buildFetchErrs[key]
}

func (m mockReader) LatestBuilds(master, builder string) ([]*messages.Build, error) {
	return m.latestBuilds[master][builder], nil
}

func (m mockReader) TestResults(masterName, builderName, stepName string, buildNumber int64) (*messages.TestResults, error) {
	return m.testResults, m.stepFetchError
}

func (m mockReader) BuildExtract(url string) (*messages.BuildExtract, error) {
	return nil, nil
}

func (m mockReader) StdioForStep(master, builder, step string, buildNum int64) ([]string, error) {
	return m.stdioForStep, m.stdioForStepError
}

func (m mockReader) JSON(url string, v interface{}) (int, error) {
	return 0, nil // Not actually used.
}

func (m mockReader) PostAlerts(alerts *messages.Alerts) error {
	return nil
}

func (m mockReader) DumpStats() {
	// Not actually used.
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
					Key:       "stale master: fake.master",
					Title:     "Stale fake.master master data",
					Body:      fmt.Sprintf("%s elapsed since last update.", 20*time.Minute),
					Time:      messages.TimeToEpochTime(time.Unix(100, 0).Add(20 * time.Minute)),
					Links:     []messages.Link{{"Master", client.MasterURL("fake.master")}},
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

	a := New(&mockReader{}, 0, 10)

	for _, test := range tests {
		a.Now = fakeNow(test.t)
		got := a.MasterAlerts(test.master, &test.be)
		if !reflect.DeepEqual(got, test.want) {
			t.Errorf("%s failed. Got %+v, want: %+v", test.name, got, test.want)
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

	a := New(&mockReader{}, 0, 10)

	for _, test := range tests {
		a.Now = fakeNow(test.t)
		got := a.BuilderAlerts(test.url, &test.be)
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
			builds: map[string]*messages.Build{
				"fake.master/fake.builder/0": {
					Steps: []messages.Step{
						{
							Name: "fake_step",
							Times: []messages.EpochTime{
								messages.TimeToEpochTime(time.Unix(10, 0)),
								messages.TimeToEpochTime(time.Unix(100, 0)),
							},
						},
					},
					Times: []messages.EpochTime{
						messages.TimeToEpochTime(time.Unix(10, 0)),
						messages.TimeToEpochTime(time.Unix(100, 0)),
					},
				},
			},
			b: messages.Builder{
				BuilderName:  "fake.builder",
				CachedBuilds: []int64{0},
			},
			wantAlerts: []messages.Alert{},
			wantErrs:   []error{},
		},
		{
			name:    "builder building for too long",
			master:  "fake.master",
			builder: "fake.builder",
			builds: map[string]*messages.Build{
				"fake.master/fake.builder/0": {
					Number: 0,
					Times: []messages.EpochTime{
						messages.TimeToEpochTime(time.Unix(10, 0)),
						messages.TimeToEpochTime(time.Unix(100, 0)),
					},
					Steps: []messages.Step{
						{
							Name: "fake_step",
							Times: []messages.EpochTime{
								messages.TimeToEpochTime(time.Unix(10, 0)),
								messages.TimeToEpochTime(time.Unix(100, 0)),
							},
						},
					},
				},
				"fake.master/fake.builder/1": {
					Number: 1,
					Steps: []messages.Step{
						{
							Name: "fake_step",
							Times: []messages.EpochTime{
								messages.TimeToEpochTime(time.Unix(10, 0)),
								messages.TimeToEpochTime(time.Unix(0, 0)),
							},
						},
					},
				},
			},
			b: messages.Builder{
				State:        messages.StateBuilding,
				BuilderName:  "fake.builder",
				CachedBuilds: []int64{0, 1},
			},
			time: time.Unix(0, 0).Add(4 * time.Hour),
			wantAlerts: []messages.Alert{
				{
					Key:      "fake.master.fake.builder.hung",
					Title:    "fake.master.fake.builder is hung in step fake_step.",
					Time:     messages.TimeToEpochTime(time.Unix(0, 0).Add(4 * time.Hour)),
					Body:     "fake.master.fake.builder has been building for 3h59m50s (last step update 1970-01-01 00:00:10 +0000 UTC), past the alerting threshold of 3h0m0s",
					Severity: 1,
					Links: []messages.Link{
						{Title: "Builder", Href: "https://build.chromium.org/p/fake.master/builders/fake.builder"},
						{Title: "Last build", Href: "https://build.chromium.org/p/fake.master/builders/fake.builder/builds/1"},
						{Title: "Last build step", Href: "https://build.chromium.org/p/fake.master/builders/fake.builder/builds/1/steps/fake_step"},
					},
				},
			},
			wantErrs: []error{},
		},
	}

	a := New(nil, 0, 10)

	for _, test := range tests {
		a.Now = fakeNow(test.time)
		a.Reader = mockReader{
			builds: test.builds,
		}
		gotAlerts, gotErrs := a.builderAlerts(test.master, test.builder, &test.b)
		if !reflect.DeepEqual(gotAlerts, test.wantAlerts) {
			t.Errorf("%s failed. Got:\n%+v, want:\n%+v", test.name, gotAlerts, test.wantAlerts)
		}
		if !reflect.DeepEqual(gotErrs, test.wantErrs) {
			t.Errorf("%s failed. Got %+v, want: %+v", test.name, gotErrs, test.wantErrs)
		}
	}
}

func TestBuilderStepAlerts(t *testing.T) {
	tests := []struct {
		name         string
		master       string
		builder      string
		recentBuilds []int64
		builds       map[string]*messages.Build
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
			builds: map[string]*messages.Build{
				"fake.master/fake.builder/0": {
					Number: 0,
					Steps: []messages.Step{
						{
							Name:    "fake_step",
							Results: []interface{}{float64(0)},
						},
					},
				},
			},
		},
		{
			name:         "one build failure",
			master:       "fake.master",
			builder:      "fake.builder",
			recentBuilds: []int64{0},
			builds: map[string]*messages.Build{
				"fake.master/fake.builder/0": {
					Number: 0,
					Steps: []messages.Step{
						{
							Name:       "fake_step",
							IsFinished: true,
							Results:    []interface{}{float64(2)},
						},
					},
					SourceStamp: messages.SourceStamp{
						Changes: []messages.Change{
							{
								Repository: "testing.git",
								Revision:   "4242",
							},
						},
					},
				},
			},
			wantAlerts: []messages.Alert{
				{
					Key:   "fake.master.fake.builder.fake_step",
					Title: "Builder step failure: fake.master.fake.builder",
					Type:  "buildfailure",
					Extension: messages.BuildFailure{
						Builders: []messages.AlertedBuilder{
							{
								Name: "fake.builder",
								URL:  "https://build.chromium.org/p/fake.master/builders/fake.builder",
							},
						},
						Reasons: []messages.Reason{
							{
								Step: "fake_step",
								URL:  "https://build.chromium.org/p/fake.master/builders/fake.builder/builds/0/steps/fake_step",
							},
						},
						RegressionRanges: []messages.RegressionRange{
							{
								Repo:      "testing.git",
								Revisions: []string{"4242"},
								Positions: []string{},
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
			builds: map[string]*messages.Build{
				"fake.master/fake.builder/0": {
					Number: 0,
					Steps: []messages.Step{
						{
							Name:       "fake_step",
							IsFinished: true,
							Results:    []interface{}{float64(2)},
						},
					},
					SourceStamp: messages.SourceStamp{
						Changes: []messages.Change{
							{
								Repository: "testing1.git",
								Revision:   "4141",
							},
						},
					},
					Properties: [][]interface{}{
						{"got_revision_cp", "refs/heads/master@{#291569}"},
					},
				},
				"fake.master/fake.builder/1": {
					Number: 1,
					Steps: []messages.Step{
						{
							Name:       "fake_step",
							IsFinished: true,
							Results:    []interface{}{float64(2)},
						},
					},
					SourceStamp: messages.SourceStamp{
						Changes: []messages.Change{
							{
								Repository: "testing1.git",
								Revision:   "4242",
							},
						},
					},
					Properties: [][]interface{}{
						{"got_revision_cp", "refs/heads/master@{#291570}"},
					},
				},
				"fake.master/fake.builder/2": {
					Number: 2,
					Steps: []messages.Step{
						{
							Name:       "fake_step",
							IsFinished: true,
							Results:    []interface{}{float64(2)},
						},
					},
					SourceStamp: messages.SourceStamp{
						Changes: []messages.Change{
							{
								Repository: "testing2.git",
								Revision:   "4343",
							},
						},
					},
					Properties: [][]interface{}{
						{"got_revision_cp", "refs/heads/master@{#291570}"},
					},
				},
				"fake.master/fake.builder/3": {
					Number: 3,
					Steps: []messages.Step{
						{
							Name:       "fake_step",
							IsFinished: true,
							Results:    []interface{}{float64(2)},
						},
					},
					SourceStamp: messages.SourceStamp{
						Changes: []messages.Change{
							{
								Repository: "testing2.git",
								Revision:   "4444",
							},
						},
					},
				},
			},
			wantAlerts: []messages.Alert{
				{
					Key:   "fake.master.fake.builder.fake_step",
					Title: "Builder step failure: fake.master.fake.builder",
					Type:  "buildfailure",
					Extension: messages.BuildFailure{
						Builders: []messages.AlertedBuilder{
							{
								Name:          "fake.builder",
								URL:           "https://build.chromium.org/p/fake.master/builders/fake.builder",
								FirstFailure:  0,
								LatestFailure: 3,
							},
						},
						Reasons: []messages.Reason{
							{
								Step: "fake_step",
								URL:  "https://build.chromium.org/p/fake.master/builders/fake.builder/builds/0/steps/fake_step",
							},
						},
						RegressionRanges: []messages.RegressionRange{
							{
								Repo:      "chromium",
								Revisions: []string{},
								Positions: []string{
									"refs/heads/master@{#291569}",
									"refs/heads/master@{#291570}",
								},
							},
							{
								Repo:      "testing1.git",
								Revisions: []string{"4141", "4242"},
								Positions: []string{},
							},
							{
								Repo:      "testing2.git",
								Revisions: []string{"4343", "4444"},
								Positions: []string{},
							},
						},
					},
				},
			},
		},
	}

	a := New(nil, 0, 10)

	for _, test := range tests {
		a.Now = fakeNow(time.Unix(0, 0))
		a.Reader = mockReader{
			builds: test.builds,
		}
		gotAlerts, gotErrs := a.builderStepAlerts(test.master, test.builder, test.recentBuilds)
		if !reflect.DeepEqual(gotAlerts, test.wantAlerts) {
			t.Errorf("%s failed. Diff:\n%+v", test.name, ansidiff.Diff(gotAlerts, test.wantAlerts))
		}
		if !reflect.DeepEqual(gotErrs, test.wantErrs) {
			t.Errorf("%s failed. Got %+v, want: %+v", test.name, gotErrs, test.wantErrs)
		}
	}
}

func TestMergeAlertsByStep(t *testing.T) {
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
					Type: "buildfailure",
					Extension: messages.BuildFailure{
						Builders: []messages.AlertedBuilder{
							{Name: "builder A"},
						},
						Reasons: []messages.Reason{
							{
								Step: "step_a",
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
					Type: "buildfailure",
					Extension: messages.BuildFailure{
						Builders: []messages.AlertedBuilder{
							{Name: "builder B"},
						},
						Reasons: []messages.Reason{
							{
								Step: "step_b",
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
					Type: "buildfailure",
					Extension: messages.BuildFailure{
						Builders: []messages.AlertedBuilder{
							{Name: "builder A"},
						},
						Reasons: []messages.Reason{
							{
								Step: "step_a",
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
					Type: "buildfailure",
					Extension: messages.BuildFailure{
						Builders: []messages.AlertedBuilder{
							{Name: "builder B"},
						},
						Reasons: []messages.Reason{
							{
								Step: "step_b",
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
					Type: "buildfailure",
					Extension: messages.BuildFailure{
						Builders: []messages.AlertedBuilder{
							{Name: "builder A"},
						},
						Reasons: []messages.Reason{
							{
								Step: "step_a",
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
					Type: "buildfailure",
					Extension: messages.BuildFailure{
						Builders: []messages.AlertedBuilder{
							{Name: "builder B"},
						},
						Reasons: []messages.Reason{
							{
								Step: "step_a",
							},
						},
						RegressionRanges: []messages.RegressionRange{
							{
								Repo: "repo.b",
							},
						},
					},
				},
				{
					Type: "buildfailure",
					Extension: messages.BuildFailure{
						Builders: []messages.AlertedBuilder{
							{Name: "builder C"},
						},
						Reasons: []messages.Reason{
							{
								Step: "step_a",
							},
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
					Title: "step_a (failing on 3 builders)",
					Type:  "buildfailure",
					Extension: messages.BuildFailure{
						Builders: []messages.AlertedBuilder{
							{Name: "builder A"},
							{Name: "builder B"},
							{Name: "builder C"},
						},
						Reasons: []messages.Reason{
							{
								Step: "step_a",
							},
						},
						RegressionRanges: []messages.RegressionRange{
							{
								Repo:      "repo.a",
								Revisions: []string{},
								Positions: []string{},
							},
							{
								Repo:      "repo.b",
								Revisions: []string{},
								Positions: []string{},
							},
							{
								Repo:      "repo.c",
								Revisions: []string{},
								Positions: []string{},
							},
						},
					},
				},
			},
		},
	}

	a := New(&mockReader{}, 0, 10)
	for _, test := range tests {
		got := a.mergeAlertsByStep(test.in)
		if !reflect.DeepEqual(got, test.want) {
			t.Errorf("%s failed. Got:\n\t%+v, want:\n\t%+v", test.name, got, test.want)
		}
	}
}

func TestUnexpected(t *testing.T) {
	tests := []struct {
		name                   string
		expected, actual, want []string
	}{
		{
			name: "empty",
			want: []string{},
		},
		{
			name:     "extra FAIL",
			expected: []string{"PASS"},
			actual:   []string{"FAIL"},
			want:     []string{"PASS", "FAIL"},
		},
		{
			name:     "FAIL FAIL",
			expected: []string{"FAIL"},
			actual:   []string{"FAIL"},
			want:     []string{},
		},
		{
			name:     "PASS PASS",
			expected: []string{"PASS"},
			actual:   []string{"PASS"},
			want:     []string{},
		},
	}

	for _, test := range tests {
		got := unexpected(test.expected, test.actual)
		if !reflect.DeepEqual(got, test.want) {
			t.Errorf("%s failed. Got: %+v, want: %+v", test.name, got, test.want)
		}
	}
}

func TestReasonsForFailure(t *testing.T) {
	tests := []struct {
		name        string
		f           stepFailure
		testResults *messages.TestResults
		want        []string
	}{
		{
			name:        "empty",
			testResults: &messages.TestResults{},
			want:        []string{},
		},
		{
			name: "GTests",
			f: stepFailure{
				step: messages.Step{
					Name: "something_tests",
				},
			},
			testResults: &messages.TestResults{
				Tests: map[string]interface{}{
					"test a": map[string]interface{}{
						"expected": "PASS",
						"actual":   "FAIL",
					},
				},
			},
			want: []string{"test a"},
		},
	}

	mc := &mockReader{}
	a := New(mc, 0, 10)

	for _, test := range tests {
		mc.testResults = test.testResults
		got := a.reasonsForFailure(test.f)
		if !reflect.DeepEqual(got, test.want) {
			t.Errorf("% s failed. Got: %+v, want: %+v", test.name, got, test.want)
		}
	}
}

func TestStepFailures(t *testing.T) {
	tests := []struct {
		name            string
		master, builder string
		b               *messages.Build
		buildNum        int64
		bCache          map[string]*messages.Build
		want            []stepFailure
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
			bCache: map[string]*messages.Build{
				"stepCheck.master/fake.builder/0": {
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
			},
			want: []stepFailure{
				{
					masterName:  "stepCheck.master",
					builderName: "fake.builder",
					build: messages.Build{
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
					step: messages.Step{
						Name:       "broken_step",
						IsFinished: true,
						Results:    []interface{}{float64(3)},
					},
				},
			},
		},
	}

	mc := &mockReader{}
	a := New(mc, 0, 10)

	for _, test := range tests {
		mc.build = test.b
		mc.bCache = test.bCache
		got, err := a.stepFailures(test.master, test.builder, test.buildNum)
		if !reflect.DeepEqual(got, test.want) {
			t.Errorf("%s failed.\nGot:\n%+v\nwant:\n%+v", test.name, got, test.want)
		}
		if !reflect.DeepEqual(err, test.wantErr) {
			t.Errorf("%s failed. Got %+v, want %+v", test.name, err, test.wantErr)
		}
	}
}

func TestStepFailureAlerts(t *testing.T) {
	tests := []struct {
		name        string
		failures    []stepFailure
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
			failures: []stepFailure{
				{
					masterName:  "fake.master",
					builderName: "fake.builder",
					build: messages.Build{
						Number: 2,
					},
					step: messages.Step{
						Name: "steps",
					},
				},
				{
					masterName:  "fake.master",
					builderName: "fake.builder",
					build: messages.Build{
						Number: 42,
					},
					step: messages.Step{
						Name: "fake_tests",
					},
				},
			},
			testResults: messages.TestResults{},
			alerts: []messages.Alert{
				{
					Key:   "fake.master.fake.builder.fake_tests",
					Title: "Builder step failure: fake.master.fake.builder",
					Type:  "buildfailure",
					Extension: messages.BuildFailure{
						Builders: []messages.AlertedBuilder{
							{
								Name:          "fake.builder",
								URL:           "https://build.chromium.org/p/fake.master/builders/fake.builder",
								FirstFailure:  42,
								LatestFailure: 42,
							},
						},
						Reasons: []messages.Reason{
							{
								Step: "fake_tests",
								URL:  "https://build.chromium.org/p/fake.master/builders/fake.builder/builds/42/steps/fake_tests",
							},
						},
						RegressionRanges: []messages.RegressionRange{},
					},
				},
			},
		},
	}

	mc := &mockReader{}
	a := New(mc, 0, 10)
	a.Now = fakeNow(time.Unix(0, 0))

	for _, test := range tests {
		mc.testResults = &test.testResults
		alerts, err := a.stepFailureAlerts(test.failures)
		if !reflect.DeepEqual(alerts, test.alerts) {
			t.Errorf("%s failed. Got:\n\t%+v, want:\n\t%+v", test.name, alerts, test.alerts)
		}
		if !reflect.DeepEqual(err, test.err) {
			t.Errorf("%s failed. Got %+v, want %+v", test.name, err, test.err)
		}
	}
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
				Steps: []messages.Step{
					{
						Name: "start step",
						Times: []messages.EpochTime{
							messages.TimeToEpochTime(time.Unix(42, 0)),
							messages.TimeToEpochTime(time.Unix(0, 0)),
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

	a := New(&mockReader{}, 0, 10)
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
		name                  string
		cfgs                  map[string]messages.MasterConfig
		master, builder, step string
		want                  bool
	}{
		{
			name:    "empty config",
			master:  "fake.master",
			builder: "fake.builder",
			step:    "fake_step",
			want:    false,
		},
		{
			name:    "specifically excluded builder",
			master:  "fake.master",
			builder: "fake.builder",
			step:    "fake_step",
			cfgs: map[string]messages.MasterConfig{
				"fake.master": {
					ExcludedBuilders: []string{"fake.builder"},
				},
			},
			want: true,
		},
		{
			name:    "specifically excluded master step",
			master:  "fake.master",
			builder: "fake.builder",
			step:    "fake_step",
			cfgs: map[string]messages.MasterConfig{
				"fake.master": {
					ExcludedSteps: []string{"fake_step"},
				},
			},
			want: true,
		},
		{
			name:    "specifically excluded builder step",
			master:  "fake.master",
			builder: "fake.builder",
			step:    "fake_step",
			cfgs: map[string]messages.MasterConfig{
				"fake.master": {
					Builders: map[string]messages.BuilderConfig{
						"fake.builder": {
							ExcludedSteps: []string{"fake_step"},
						},
					},
				},
			},
			want: true,
		},
		{
			name:    "wildcard builder excluded",
			master:  "fake.master",
			builder: "fake.builder",
			step:    "fake_step",
			cfgs: map[string]messages.MasterConfig{
				"fake.master": {
					ExcludedBuilders: []string{"*"},
				},
			},
			want: true,
		},
	}

	a := New(&mockReader{}, 0, 10)
	for _, test := range tests {
		a.MasterCfgs = test.cfgs
		got := a.excludeFailure(test.master, test.builder, test.step)
		if got != test.want {
			t.Errorf("%s failed. Got: %+v, want: %+v", test.name, got, test.want)
		}
	}
}
