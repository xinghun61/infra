// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package dashboard

import (
	"reflect"
	"testing"
	"time"

	"golang.org/x/net/context"

	"github.com/luci/gae/service/datastore"
	"github.com/luci/luci-go/appengine/gaetesting"

	"infra/appengine/dashboard/backend"
)

var (
	incidentStartIdx = datastore.IndexDefinition{
		Kind:     "ServiceIncident",
		Ancestor: true,
		SortBy: []datastore.IndexColumn{
			{
				Property: "Open",
			},
			{
				Property: "StartTime",
			},
		},
	}
	incidentIneqEndIdx = datastore.IndexDefinition{
		Kind:     "ServiceIncident",
		Ancestor: true,
		SortBy: []datastore.IndexColumn{
			{
				Property: "Open",
			},
			{
				Property: "EndTime",
			},
		},
	}
	indexes = []*datastore.IndexDefinition{&incidentStartIdx, &incidentIneqEndIdx}
)

var baseDate = time.Date(2017, time.April, 11, 23, 0, 0, 0, time.UTC)

var testService = backend.Service{
	ID:   "testservice",
	Name: "Test Service",
	SLA:  "www.google.com",
}
var testOpenIncident = backend.ServiceIncident{
	ID:        "cqRedAlert",
	Severity:  backend.SeverityRed,
	Open:      true,
	StartTime: baseDate,
}

var testCloseIncident = backend.ServiceIncident{
	ID:        "cqYellowAlert",
	Severity:  backend.SeverityYellow,
	Open:      false,
	StartTime: baseDate.AddDate(0, 0, -4),
	EndTime:   baseDate.AddDate(0, 0, -3),
}

var testServiceAnother = backend.Service{
	ID:   "testserviceanother",
	Name: "Test Service another",
}

func newTestContext() context.Context {
	ctx := gaetesting.TestingContext()
	testing := datastore.GetTestable(ctx)
	testing.Consistent(true)
	testing.AddIndexes(indexes...)
	return ctx
}

func TestCreateServicesPageData(t *testing.T) {
	ctx := newTestContext()
	datastore.Put(ctx, &testService)
	testOpenInc := testOpenIncident
	testOpenInc.ServiceKey = datastore.NewKey(ctx, "Service", testService.ID, 0, nil)
	datastore.Put(ctx, &testOpenInc)

	testCloseInc := testCloseIncident
	testCloseInc.ServiceKey = datastore.NewKey(ctx, "Service", testService.ID, 0, nil)
	datastore.Put(ctx, &testCloseInc)

	datastore.Put(ctx, &testServiceAnother)

	wantSLA := []TemplateService{
		{testService, []backend.ServiceIncident{testOpenInc, testCloseInc}},
	}
	wantNonSLA := []TemplateService{
		{testServiceAnother, []backend.ServiceIncident{}},
	}
	sla, nonSLA, err := createServicesPageData(ctx, baseDate.AddDate(0, 0, -5), baseDate.AddDate(0, 0, -1))
	if err != nil {
		t.Errorf("did not expect error, found %v", err)
	}
	if !reflect.DeepEqual(sla, wantSLA) {
		t.Errorf("found %v want %v", sla, wantSLA)
	}
	if !reflect.DeepEqual(nonSLA, wantNonSLA) {
		t.Errorf("found %v want %v", nonSLA, wantNonSLA)
	}
}
