// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package dashboard

import (
	"reflect"
	"testing"

	"golang.org/x/net/context"

	"github.com/luci/gae/service/datastore"
	"github.com/luci/luci-go/appengine/gaetesting"

	"infra/appengine/dashboard/backend"
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

var testService = backend.Service{
	ID:   "testservice",
	Name: "Test Service",
	SLA:  "www.google.com",
}
var testIncident = backend.ServiceIncident{
	ID:       "cqRedAlert",
	Severity: backend.SeverityRed,
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
	testInc := testIncident
	testInc.ServiceKey = datastore.NewKey(ctx, "Service", testService.ID, 0, nil)
	datastore.Put(ctx, &testInc)
	datastore.Put(ctx, &testServiceAnother)

	wantSLA := []TemplateService{
		{testService, []backend.ServiceIncident{testInc}},
	}
	wantNonSLA := []TemplateService{
		{testServiceAnother, []backend.ServiceIncident{}},
	}

	sla, nonSLA, err := createServicesPageData(ctx)
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
