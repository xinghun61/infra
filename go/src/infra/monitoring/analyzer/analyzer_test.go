// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package analyzer

import (
	"fmt"
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

type mockClient struct {
	build                           *messages.Builds
	testResults                     *messages.TestResults
	buildFetchError, stepFetchError error
}

func (m mockClient) Build(mn, bn string, bID int64) (*messages.Builds, error) {
	return m.build, m.buildFetchError
}

func (m mockClient) TestResults(masterName, builderName, stepName string, buildNumber int64) (*messages.TestResults, error) {
	return m.testResults, m.stepFetchError
}

func (m mockClient) BuildExtracts(urls []string) (map[string]*messages.BuildExtract, map[string]error) {
	return nil, nil
}

func (m mockClient) JSON(url string, v interface{}) (int, error) {
	return 0, nil // Not actually used.
}

func (m mockClient) DumpStats() {
	// Not actually used.
}

func TestMasterAlerts(t *testing.T) {
	tests := []struct {
		name string
		url  string
		be   messages.BuildExtract
		t    time.Time
		want []messages.Alert
	}{
		{
			name: "empty",
			url:  "http://fake-empty",
			want: []messages.Alert{},
		},
		{
			name: "Not stale master",
			url:  "http://fake-not-stale",
			be: messages.BuildExtract{
				CreatedTimestamp: messages.EpochTime(100),
			},
			t:    time.Unix(100, 0),
			want: []messages.Alert{},
		},
		{
			name: "Stale master",
			url:  "http://fake.master",
			be: messages.BuildExtract{
				CreatedTimestamp: messages.EpochTime(100),
			},
			t: time.Unix(100, 0).Add(StaleMasterThreshold * 2),
			want: []messages.Alert{
				{
					Key:   "stale master: http://fake.master",
					Title: "Stale Master Data",
					Body:  fmt.Sprintf("%s elapsed since last update.", 2*StaleMasterThreshold),
					Time:  messages.TimeToEpochTime(time.Unix(100, 0).Add(StaleMasterThreshold * 2)),
					Links: []messages.Link{{"Master Url", "http://fake.master"}},
				},
			},
		},
		{
			name: "Future master",
			url:  "http://fake.master",
			be: messages.BuildExtract{
				CreatedTimestamp: messages.EpochTime(110),
			},
			t:    time.Unix(100, 0),
			want: []messages.Alert{},
		},
	}

	a := New(&mockClient{}, 10)

	for _, test := range tests {
		now = fakeNow(test.t)
		got := a.MasterAlerts(test.url, &test.be)
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
			wantBuilders: []messages.Alert{},
			wantMasters:  []messages.Alert{},
		},
		{
			name: "No Alerts",
			url:  "http://fake.master",
			be: messages.BuildExtract{
				CreatedTimestamp: messages.EpochTime(100),
			},
			t:            time.Unix(100, 0),
			wantBuilders: []messages.Alert{},
			wantMasters:  []messages.Alert{},
		},
	}

	a := New(&mockClient{}, 10)

	for _, test := range tests {
		now = fakeNow(test.t)
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
		b          messages.Builders
		builds     *messages.Builds
		wantAlerts []messages.Alert
		wantErrs   []error
	}{
		{
			name:       "empty",
			wantAlerts: []messages.Alert{},
			wantErrs:   []error{},
		},
		{
			name:    "builders ok",
			master:  "fake.master",
			builder: "fake.builder",
			builds:  &messages.Builds{},
			b: messages.Builders{
				BuilderName:   "fake.builder",
				CachedBuilds:  []int64{0, 1, 2, 3},
				CurrentBuilds: []int64{5, 6, 7, 8},
			},
			wantAlerts: []messages.Alert{},
			wantErrs:   []error{},
		},
	}

	a := New(nil, 10)

	for _, test := range tests {
		a.Client = mockClient{
			build: test.builds,
		}
		gotAlerts, gotErrs := a.builderAlerts(test.master, test.builder, &test.b)
		if !reflect.DeepEqual(gotAlerts, test.wantAlerts) {
			t.Errorf("%s failed. Got %+v, want: %+v", test.name, gotAlerts, test.wantAlerts)
		}
		if !reflect.DeepEqual(gotErrs, test.wantErrs) {
			t.Errorf("%s failed. Got %+v, want: %+v", test.name, gotErrs, test.wantErrs)
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
			name: "empty",
		},
		{
			name: "GTests",
			f: stepFailure{
				step: messages.Steps{
					Name: "something_tests",
				},
			},
			testResults: &messages.TestResults{
				Tests: map[string]messages.TestResult{
					"test a": messages.TestResult{
						Expected: "PASS",
						Actual:   "FAIL",
					},
				},
			},
			want: []string{"test a"},
		},
	}

	mc := &mockClient{}
	a := New(mc, 10)

	for _, test := range tests {
		mc.testResults = test.testResults
		got := a.reasonsForFailure(test.f)
		if !reflect.DeepEqual(got, test.want) {
			t.Errorf("% s failed. Got: %+v, want: %+v", test.name, got, test.want)
		}
	}
}

func TestStepFailureAlerts(t *testing.T) {
	tests := []struct {
		name        string
		failures    []stepFailure
		testResults *messages.TestResults
		wantAlerts  []messages.Alert
		wantErr     error
	}{
		{
			name:       "empty",
			wantAlerts: []messages.Alert{},
		},
		{
			name: "build failure: test step",
			failures: []stepFailure{
				{
					masterName:  "fake.master",
					builderName: "fake_builder",
					step: messages.Steps{
						Name: "something_tests",
					},
				},
			},
			testResults: &messages.TestResults{
				Tests: map[string]messages.TestResult{
					"test_a": messages.TestResult{
						Expected: "PASS",
						Actual:   "FAIL",
					},
				},
			},
			wantAlerts: []messages.Alert{
				{
					Key:   "fake.master.fake_builder.something_tests.test_a",
					Title: "Builder step failure",
					Type:  "buildfailure",
					Extension: messages.BuildFailure{
						Builders: []messages.AlertedBuilder{
							{
								Name:          "fake_builder",
								FirstFailure:  0,
								LatestFailure: 1,
								URL:           "https://build.chromium.org/p/fake.master/builders/fake_builder/builds/0/steps/something_tests",
							},
						},
						Reasons: []messages.Reason{
							{
								TestName: "test_a",
								Step:     "something_tests",
							},
						},
					},
				},
			},
		},
	}

	mc := &mockClient{}
	a := New(mc, 10)

	now = fakeNow(time.Unix(0, 0))
	for _, test := range tests {
		mc.testResults = test.testResults
		gotAlerts, gotErr := a.stepFailureAlerts(test.failures)
		if !reflect.DeepEqual(gotAlerts, test.wantAlerts) {
			t.Errorf("%s failed.\n\tGot:\n\t%+v\n\twant:\n\t%+v.", test.name, gotAlerts, test.wantAlerts)
		}
		if !reflect.DeepEqual(gotErr, test.wantErr) {
			t.Errorf("%s failed. Got: %+v want: %+v.", test.name, gotErr, test.wantErr)
		}
	}
}

func TestStepFailures(t *testing.T) {
	tests := []struct {
		name            string
		master, builder string
		b               *messages.Builds
		bID             int64
		bCache          map[string]*messages.Builds
		want            []stepFailure
		wantErr         error
	}{
		{
			name:    "empty",
			master:  "fake.master",
			builder: "fake.builder",
		},
		{
			name:    "breaking step",
			master:  "stepCheck.master",
			builder: "fake.builder",
			bID:     0,
			bCache: map[string]*messages.Builds{
				"stepCheck.master/fake.builder/0.json": &messages.Builds{
					Steps: []messages.Steps{
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
					build: messages.Builds{
						Steps: []messages.Steps{
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
					step: messages.Steps{
						Name:       "broken_step",
						IsFinished: true,
						Results:    []interface{}{float64(3)},
					},
				},
			},
		},
	}

	mc := &mockClient{}
	a := New(mc, 10)

	for _, test := range tests {
		mc.build = test.b
		a.bCache = test.bCache
		got, err := a.stepFailures(test.master, test.builder, test.bID)
		if !reflect.DeepEqual(got, test.want) {
			t.Errorf("%s failed.\nGot:\n%+v\nwant:\n%+v", test.name, got, test.want)
		}
		if !reflect.DeepEqual(err, test.wantErr) {
			t.Errorf("%s failed. Got %+v, want %+v", test.name, err, test.wantErr)
		}
	}
}
