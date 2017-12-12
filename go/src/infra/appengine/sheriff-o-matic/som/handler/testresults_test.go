// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package handler

import (
	"fmt"
	"reflect"
	"testing"
	"time"

	"infra/monitoring/messages"

	"cloud.google.com/go/bigquery"

	"go.chromium.org/luci/server/router"

	"google.golang.org/api/iterator"
)

var alertedBuilders = []messages.AlertedBuilder{
	{Name: "builderOne", Master: "masterOne"},
	{Name: "builderTwo", Master: "masterOne"},
	{Name: "builderThree", Master: "masterTwo"},
}

func TestGetBuildersByMaster(t *testing.T) {
	expectedMap := map[string][]string{
		"masterOne": {"builderOne", "builderTwo"},
		"masterTwo": {"builderThree"},
	}
	buildersMap := getBuildersByMaster(alertedBuilders)
	if !reflect.DeepEqual(expectedMap, buildersMap) {
		t.Errorf("expected map: %v. Found map: %v", expectedMap, buildersMap)
	}
}

type mockTestFailure struct{}

func (t *mockTestFailure) Signature() string {
	return "stepName and testNames"
}
func (t *mockTestFailure) Kind() string {
	return "test"
}
func (t *mockTestFailure) Severity() messages.Severity {
	return messages.NoSeverity
}
func (t *mockTestFailure) Title(bs []*messages.BuildStep) string {
	return "failing somewhere"
}

type fakeRaw struct{}

func (f *fakeRaw) Signature() string {
	return "stepName and testNames"
}
func (f *fakeRaw) Kind() string {
	return "fake"
}
func (f *fakeRaw) Severity() messages.Severity {
	return messages.NoSeverity
}
func (f *fakeRaw) Title(bs []*messages.BuildStep) string {
	return "failing somewhere"
}

type fakeExtension struct{}

func TestIsTestFailure(t *testing.T) {
	testAlert := messages.Alert{
		Extension: messages.BuildFailure{
			Reason: &messages.Reason{
				Raw: &mockTestFailure{},
			},
		},
	}
	if !isTestFailure(testAlert) {
		t.Error("expected true, found false")
	}

	alert := messages.Alert{Extension: fakeExtension{}}
	if isTestFailure(alert) {
		t.Error("expected false, found true")
	}

	fakeAlert := messages.Alert{
		Extension: messages.BuildFailure{
			Reason: &messages.Reason{
				Raw: &fakeRaw{},
			},
		},
	}
	if isTestFailure(fakeAlert) {
		t.Error("expected false, found true")
	}
}

func TestGetBQClient(t *testing.T) {
	ctx := &router.Context{Context: newTestContext()}
	_, err := getBQClient(ctx.Context)
	if err == nil {
		t.Errorf("expected error, auth library should not be configured")
	}
}

var rowResultsOne = []messages.Results{
	{
		BuildNumber: 1,
		Actual:      []string{"FAIL"},
		Expected:    []string{"PASS"},
	},
	{
		BuildNumber: 2,
		Actual:      []string{"FAIL"},
		Expected:    []string{"PASS"},
	},
}

// mockBQIterator implements bqIterator interface
type mockBQIterator struct {
	CurrentResult int
	TotalResults  int
	Results       []messages.Results
	ThrowError    bool
}

func (iter *mockBQIterator) Next(result interface{}) error {
	if iter.ThrowError {
		return fmt.Errorf("there's been an error")
	}
	if result, ok := result.(*messages.Results); ok {
		if iter.CurrentResult >= iter.TotalResults {
			return iterator.Done
		}
		current := iter.Results[iter.CurrentResult]
		result.BuildNumber = current.BuildNumber
		result.Actual = current.Actual
		result.Expected = current.Expected
		iter.CurrentResult++
		return nil
	}
	return iterator.Done
}

func TestExtractResults(t *testing.T) {
	ctx := &router.Context{Context: newTestContext()}

	foundResults, err := extractResults(ctx.Context, &mockBQIterator{Results: rowResultsOne, TotalResults: 2})
	if err != nil {
		t.Errorf("expected no error, found: %v", err)
	}
	if !reflect.DeepEqual(foundResults, rowResultsOne) {
		t.Errorf("expected: %v, found: %v", rowResultsOne, foundResults)
	}

	foundResults, err = extractResults(ctx.Context, &mockBQIterator{Results: []messages.Results{}})
	if err != nil {
		t.Errorf("expected no error, found: %v", err)
	}
	if !reflect.DeepEqual(foundResults, []messages.Results{}) {
		t.Errorf("expected: %v, found: %v", []messages.Results{}, foundResults)
	}

	foundResults, err = extractResults(ctx.Context, &mockBQIterator{ThrowError: true})
	if err == nil {
		t.Errorf("expected error, found no error")
	}
}

func TestGetTestResultsQuery(t *testing.T) {
	diff := 5
	startTime := time.Now().AddDate(0, 0, -diff)
	got := getTestResultsQuery(startTime)
	want := fmt.Sprintf(testResultsQuery, diff)
	if !reflect.DeepEqual(got, want) {
		t.Errorf("expected: %s, found: %s", want, got)
	}

	diff = 1
	startTime = time.Now().AddDate(0, 0, -diff)
	got = getTestResultsQuery(startTime)
	want = fmt.Sprintf(testResultsQuery, diff)
	if !reflect.DeepEqual(got, want) {
		t.Errorf("expected: %s, found: %s", want, got)
	}
}

func TestMakeQueryParameters(t *testing.T) {
	master, builder, step, test := "testMaster", "testBuilder", "testStep", "testName"
	want := []bigquery.QueryParameter{
		{Name: "master", Value: master},
		{Name: "builder", Value: builder},
		{Name: "step", Value: step},
		{Name: "testname", Value: test},
	}
	got := makeQueryParameters(test, master, builder, step)
	if !reflect.DeepEqual(got, want) {
		t.Errorf("expected: %v, found: %v", want, got)
	}
}
