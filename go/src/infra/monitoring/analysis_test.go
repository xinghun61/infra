// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"fmt"
	"reflect"
	"testing"
	"time"

	"infra/monitoring/messages"
)

func fakeNow(t time.Time) func() time.Time {
	return func() time.Time {
		return t
	}
}

func TestStaleMasterAlerts(t *testing.T) {
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

	for _, test := range tests {
		now = fakeNow(test.t)
		got := staleMasterAlerts(test.url, &test.be)
		if !reflect.DeepEqual(got, test.want) {
			t.Errorf("%s failed. Want: %v Got %v", test.name, test.want, got)
		}
	}
}

func TestMasterAlerts(t *testing.T) {
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

	for _, test := range tests {
		now = fakeNow(test.t)
		gotBuilders, gotMasters := MasterAlerts(test.url, &test.be)
		if !reflect.DeepEqual(gotBuilders, test.wantBuilders) {
			t.Errorf("%s failed. Want builders: %v Got %v", test.name, test.wantBuilders, gotBuilders)
		}
		if !reflect.DeepEqual(gotMasters, test.wantMasters) {
			t.Errorf("%s failed. Want masters: %v Got %v", test.name, test.wantMasters, gotMasters)
		}
	}
}
