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

	indexes = []*datastore.IndexDefinition{&serviceIdx, &incidentIdx}
)

type getServiceTest struct {
	inputID    string
	expService *Service
	expError   error
}

var testService = &Service{
	ID:   "testservice",
	Name: "Test Service",
	SLA:  "www.google.com",
}

var testServiceAnother = &Service{
	ID:   "testserviceanother",
	Name: "Test Service another",
	SLA:  "www.another.com",
}

var testIncs = []ServiceIncident{
	{
		ID:       "cqRedAlert",
		Severity: SeverityRed,
	},
	{
		ID:       "cqYellowAlert",
		Severity: SeverityYellow,
	},
	{
		ID:       "monorailRedAlert",
		Severity: SeverityRed,
	},
	{
		ID:       "monorailYellowAlert",
		Severity: SeverityYellow,
	},
}

func newTestContext() context.Context {
	ctx := gaetesting.TestingContext()
	testing := datastore.GetTestable(ctx)
	testing.Consistent(true)
	testing.AddIndexes(indexes...)
	return ctx
}

func TestGetIncident(t *testing.T) {
	ctx := newTestContext()
	datastore.Put(ctx, testService)
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
	datastore.Put(ctx, testService)

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

	datastore.Put(ctx, testServiceAnother)

	// Test with Service that has ServiceIncidents children.
	want := []ServiceIncident{*testIncOne, *testIncTwo}
	incidents, err := GetServiceIncidents(ctx, testService.ID)
	if err != nil {
		t.Errorf("Expect no errors. Found: %v", err)
	}
	if !reflect.DeepEqual(incidents, want) {
		t.Errorf("Expected incidents:%v. Found: %v", want, incidents)
	}

	// Test with Service that has no ServiceIncidents children.
	want = []ServiceIncident{}
	incidents, err = GetServiceIncidents(ctx, testServiceAnother.ID)
	if err != nil {
		t.Errorf("Expect no errors. Found: %v", err)
	}
	if !reflect.DeepEqual(incidents, want) {
		t.Errorf("Expected incidents:%v. Found: %v", want, incidents)
	}

}

func TestGetService(t *testing.T) {
	ctx := newTestContext()
	datastore.Put(ctx, testService)

	// Test GetService with a service that exists.
	service, err := GetService(ctx, testService.ID)
	if err != nil {
		t.Errorf("Expect no errors. Found: %v", err)
	}
	if !reflect.DeepEqual(testService, service) {
		t.Errorf("Expected service: %v. Found service: %v",
			testService, service)
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

func TestAddIncident(t *testing.T) {
	ctx := newTestContext()
	datastore.Put(ctx, testService)
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
	datastore.Put(ctx, testService)
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
	if (newIncident.EndTime == time.Time{}) {
		t.Error("Incident was not closed, EndTime is not set")
	}

	// Test that passing a nonexistent ServiceIncident throws an error.
	if err := CloseIncident(ctx, testIncident.ID, "ghostservice"); err == nil {
		t.Errorf("expected error. found nil error.")
	}
}
