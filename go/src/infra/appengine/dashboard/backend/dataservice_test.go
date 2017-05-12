// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package backend

import (
	"reflect"
	"testing"
	"time"

	"golang.org/x/net/context"

	"github.com/luci/gae/service/datastore"
	"github.com/luci/luci-go/appengine/gaetesting"
)

var (
	serviceIdx = datastore.IndexDefinition{
		Kind:     "Service",
		Ancestor: true,
		SortBy: []datastore.IndexColumn{
			{
				Property:   "Name",
				Descending: true,
			},
		},
	}

	incidentIdx = datastore.IndexDefinition{
		Kind:     "ServiceIncident",
		Ancestor: true,
		SortBy: []datastore.IndexColumn{
			{
				Property:   "ID",
				Descending: true,
			},
		},
	}
	incidentIneqIdx = datastore.IndexDefinition{
		Kind:     "ServiceIncident",
		Ancestor: true,
		SortBy: []datastore.IndexColumn{
			{
				Property: "StartTime",
			},
		},
	}

	indexes = []*datastore.IndexDefinition{&serviceIdx, &incidentIdx, &incidentIneqIdx}
)

type getServiceTest struct {
	inputID    string
	expService *Service
	expError   error
}

var testService = Service{
	ID:   "testservice",
	Name: "Test Service",
	SLA:  "www.google.com",
}

var testServiceAnother = Service{
	ID:   "testserviceanother",
	Name: "Test Service another",
	SLA:  "www.another.com",
}

var now = time.Now().UTC().Truncate(time.Minute)
var baseDate = time.Date(2017, time.April, 11, 23, 0, 0, 0, time.UTC)

var testIncs = []ServiceIncident{
	{
		ID:        "cqRedAlert",
		Severity:  SeverityRed,
		StartTime: baseDate.AddDate(0, 0, 5),
		Open:      true,
	},
	{
		ID:        "cqYellowAlert",
		Severity:  SeverityYellow,
		StartTime: baseDate.AddDate(0, 0, -2),
		EndTime:   now,
		Open:      false,
	},
	{
		ID:        "monorailRedAlert",
		Severity:  SeverityRed,
		StartTime: baseDate,
		Open:      true,
	},
	{
		ID:        "monorailYellowAlert",
		Severity:  SeverityYellow,
		StartTime: baseDate,
		EndTime:   now,
		Open:      false,
	},
}

func newTestContext() context.Context {
	ctx := gaetesting.TestingContext()
	testing := datastore.GetTestable(ctx)
	testing.Consistent(true)
	testing.AddIndexes(indexes...)
	return ctx
}

func TestBuildQuery(t *testing.T) {
	baseQuery := datastore.NewQuery("ServiceIncident")
	before := time.Now().UTC()
	after := before.AddDate(0, 0, -2).UTC()

	testCases := []struct {
		wantQuery *datastore.Query
		queryOpts QueryOptions
		timeField string
		wantErr   bool
	}{
		{
			wantQuery: baseQuery.Eq("Open", true),
			queryOpts: QueryOptions{Status: IncidentStatusOpen},
			timeField: "",
			wantErr:   false,
		},
		{
			wantQuery: baseQuery.Eq("Open", false).Gte("StartTime", after).Lte("StartTime", before),
			queryOpts: QueryOptions{
				After:  after,
				Before: before,
				Status: IncidentStatusClosed,
			},
			timeField: "StartTime",
			wantErr:   false,
		},
		{
			wantQuery: nil,
			queryOpts: QueryOptions{
				After:  after,
				Before: before,
				Status: IncidentStatusClosed,
			},
			timeField: "",
			wantErr:   true,
		},
	}
	for i, tc := range testCases {
		query, err := tc.queryOpts.BuildQuery(baseQuery, tc.timeField)
		if tc.wantErr {
			if err == nil {
				t.Errorf("%d: expected error, found: %s", i, err)
			}
		} else {
			_, _ = tc.wantQuery.Finalize()
			if err != nil {
				t.Errorf("%d: expected no error, found: %s", i, err)
			}
			if !reflect.DeepEqual(query, tc.wantQuery) {
				t.Errorf("%d: expected query: %+v, found: %+v", i, tc.wantQuery, query)
			}
		}
	}
}

func TestGetIncident(t *testing.T) {
	ctx := newTestContext()
	datastore.Put(ctx, &testService)
	testInc := &testIncs[0]
	// Set testService as testInc's ancestor.
	testInc.ServiceKey = datastore.NewKey(ctx, "Service", testService.ID, 0, nil)
	datastore.Put(ctx, testInc)

	// Test GetIncident with an incident that exists.
	incident, err := GetIncident(ctx, testInc.ID, testService.ID)
	if err != nil {
		t.Errorf("Expect no errors. Found: %v", err)
	}
	if !reflect.DeepEqual(testInc, incident) {
		t.Errorf("Expected incident: %v. Found incident: %v",
			testInc, incident)
	}

	// Test GetIncident with a nonexistent incident.
	incident, err = GetIncident(ctx, "booInc", "booService")
	if err != nil {
		t.Errorf("Expect no errors. Found: %v", err)
	}
	if incident != nil {
		t.Errorf("Expected nil incident. Found: %v", incident)
	}
}

func TestGetServiceIncidents(t *testing.T) {
	ctx := newTestContext()
	datastore.Put(ctx, &testService)

	testIncOne := &testIncs[0]
	testIncOne.ServiceKey = datastore.NewKey(ctx, "Service", testService.ID, 0, nil)
	datastore.Put(ctx, testIncOne)

	testIncTwo := &testIncs[1]
	testIncTwo.ServiceKey = datastore.NewKey(ctx, "Service", testService.ID, 0, nil)
	datastore.Put(ctx, testIncTwo)

	testIncThree := &testIncs[2]
	datastore.Put(ctx, testIncThree)

	testIncFour := &testIncs[3]
	datastore.Put(ctx, testIncFour)

	datastore.Put(ctx, &testServiceAnother)

	testCases := []struct {
		want      []ServiceIncident
		serviceID string
		queryOpts *QueryOptions
	}{
		// Test with Service that has ServiceIncidents children.
		{[]ServiceIncident{*testIncOne, *testIncTwo}, testService.ID, nil},
		// Test with Service that has no ServiceIncidents children.
		{[]ServiceIncident{}, testServiceAnother.ID, nil},
		// Test with Service for only open ServiceIncidents.
		{[]ServiceIncident{*testIncOne}, testService.ID, &QueryOptions{
			Status: IncidentStatusOpen}},
		// Test with Service for only closed ServiceIncidents.
		{[]ServiceIncident{*testIncTwo}, testService.ID, &QueryOptions{
			Status: IncidentStatusClosed}},
		// Test with Service using StartTime upper/lower limit.
		{[]ServiceIncident{*testIncTwo}, testService.ID, &QueryOptions{
			After:  baseDate.AddDate(0, 0, -5),
			Before: baseDate},
		},
		{[]ServiceIncident{}, testService.ID, &QueryOptions{
			After:  baseDate.AddDate(0, 0, -1),
			Before: baseDate},
		},
	}
	for i, tc := range testCases {
		incidents, err := GetServiceIncidents(ctx, tc.serviceID, tc.queryOpts)
		if err != nil {
			t.Errorf("%d: Expect no errors. Found: %v", i, err)
		}
		if !reflect.DeepEqual(incidents, tc.want) {
			t.Errorf("%d: Expected incidents:%v. Found: %v", i, tc.want, incidents)
		}
	}
}

func TestGetService(t *testing.T) {
	ctx := newTestContext()
	datastore.Put(ctx, &testService)

	// Test GetService with a service that exists.
	service, err := GetService(ctx, testService.ID)
	if err != nil {
		t.Errorf("Expect no errors. Found: %v", err)
	}
	if !reflect.DeepEqual(&testService, service) {
		t.Errorf("Expected service: %v. Found service: %v",
			&testService, service)
	}

	// Test GetService with a nonexistent service.
	service, err = GetService(ctx, "ghost")
	if err != nil {
		t.Errorf("Expect no errors. Found: %v", err)
	}
	if service != nil {
		t.Errorf("Expected nil service. Found: %v", service)
	}
}

func TestGetAllServices(t *testing.T) {
	ctx := newTestContext()

	// Test GetAllServices with no Service entities stored.
	want := []Service{}
	services, err := GetAllServices(ctx)
	if err != nil {
		t.Errorf("Expect no errors. Found: %v", err)
	}
	if !reflect.DeepEqual(services, want) {
		t.Errorf("Want %v, found %v", services, want)
	}

	// Test GetAllServices
	datastore.Put(ctx, &testService)
	datastore.Put(ctx, &testServiceAnother)
	want = []Service{testService, testServiceAnother}
	services, err = GetAllServices(ctx)
	if err != nil {
		t.Errorf("Expect no errors. Found: %v", err)
	}
	if !reflect.DeepEqual(services, want) {
		t.Errorf("Want %v, found %v", services, want)
	}
}

func TestAddIncident(t *testing.T) {
	ctx := newTestContext()
	datastore.Put(ctx, &testService)
	testIncident := &testIncs[0]
	// Set testService as testIncident's ancestor.
	testServiceKey := datastore.NewKey(ctx, "Service", testService.ID, 0, nil)
	testIncident.ServiceKey = testServiceKey
	datastore.Put(ctx, testIncident)
	// Test Incident was successfully added to datastore.
	newIncID := "cqYellowAlert"
	if err := AddIncident(ctx, newIncID, testService.ID, SeverityRed); err != nil {
		t.Errorf("expected no error. found: %v", err)
	}
	incidentKey := datastore.NewKey(ctx, "ServiceIncident", newIncID, 0, testServiceKey)
	existsResults, err := datastore.Exists(ctx, incidentKey)
	if err != nil {
		t.Errorf("error while checking if Incident was successfully stored: %v", err)
	}
	if !existsResults.Any() {
		t.Errorf("incident was not found to exist in datastore: %v", existsResults)
	}
	// Test that a nonexistent Service throws an error.
	if err = AddIncident(ctx, "monorailRedAlert", "ghostservice", SeverityRed); err == nil {
		t.Error("expected error. found no error")
	}
	// Test that an Incident already in datastore does not get added again.
	if err = AddIncident(ctx, testIncident.ID, testService.ID, SeverityRed); err == nil {
		t.Error("expected error. found no error")
	}
}
func TestCloseIncident(t *testing.T) {
	ctx := newTestContext()
	datastore.Put(ctx, &testService)
	testIncident := &testIncs[0]
	// Set testService as testIncident's ancestor.
	testServiceKey := datastore.NewKey(ctx, "Service", testService.ID, 0, nil)
	testIncident.ServiceKey = testServiceKey
	datastore.Put(ctx, testIncident)

	// Test an ServiceIncident's EndTime gets correctly filled in.
	if err := CloseIncident(ctx, testIncident.ID, testService.ID); err != nil {
		t.Errorf("expected no error. found: %v", err)
	}
	newIncident := &ServiceIncident{ID: testIncident.ID, ServiceKey: testServiceKey}
	if err := datastore.Get(ctx, newIncident); err != nil {
		t.Errorf("expected no error. found: %v", err)
	}
	if newIncident.EndTime == (time.Time{}) {
		t.Error("Incident was not fully closed, EndTime is not set")
	}
	if newIncident.Open {
		t.Error("Incident was not fully closed, Open was not set to false")
	}

	// Test that passing a nonexistent ServiceIncident throws an error.
	if err := CloseIncident(ctx, testIncident.ID, "ghostservice"); err == nil {
		t.Errorf("expected error. found nil error.")
	}
}
