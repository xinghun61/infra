// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package jsoncfg

import (
	"testing"
	"time"

	"infra/appengine/rotang"

	"github.com/kylelemons/godebug/pretty"
)

var (
	jsonRotation = `
		{
			"rotation_config": {
					"calendar_name": "testCalendarLink@testland.com",
					"event_description": "Test description",
					"event_title": "Chrome OS Build Sheriff",
					"owners": [
						"leowner@google.com"
					],
					"people_per_rotation": 1,
					"reminder_email_body": "Some reminder",
					"reminder_email_subject": "Chrome OS build sheriff reminder",
					"reminder_email_advance_days": 2,
					"rotation_length": 5,
					"strict_title": true,
					"temporarily_removed": {
						"email_address": "superadmin@google.com",
						"full_name": "Super Admin"
					}
				},
				"rotation_list_pacific": {
					"person": [
						{
							"email_address": "letestbot@google.com",
							"full_name": "French Test Bot"
						},
						{
							"email_address": "testsheriff@google.com",
							"full_name": "Test Sheriff"
						},
						{
							"email_address": "anothersheriff@google.com",
							"full_name": "Yet Another Test Sheriff"
						}
					]
				}
		}`
	codesearchRotation = `
		{
			"rotation_config": [
				{
					"calendar_name": "testCalendarLink@testland.com",
					"event_description": "Triage for Codesearch Issues.",
					"event_title": "ChOps DevX Codesearch Triage Rotation.",
					"owners": [
						"test+one@google.com",
						"theboss@google.com"
					],
					"people_per_rotation": 1,
					"reminder_email_advance_days": 2,
					"reminder_email_body": "This is a friendly reminder that you are the Codesearch bug triager for %s. Please do daily bug triage of http://go/cr-cs-triage.",
					"reminder_email_subject": "ChOps DevX Codesearch Triage reminder",
					"rotation_length": 5,
					"strict_title": true
				}
			],
			"rotation_list_default": {
				"person": [
					{
						"email_address": "test+one@google.com",
						"full_name": "Test Bot"
					},
					{
						"email_address": "test+two@google.com",
						"full_name": "Test Sheriff"
					},
					{
						"email_address": "test+three@google.com",
						"full_name": "Yet Another Test Sheriff"
					},
					{
						"email_address": "test+four@google.com",
						"full_name": "Another codesearch wiz"
					}
				]
			}
		}`
)

func TestReadJson(t *testing.T) {
	usLocation, err := time.LoadLocation(pacificTZ)
	if err != nil {
		t.Fatalf("time.LoadLocation(%q) failed: %v", pacificTZ, err)
	}
	euLocation, err := time.LoadLocation(euTZ)
	if err != nil {
		t.Fatalf("time.LoadLocation(%q) failed: %v", euTZ, err)
	}

	tests := []struct {
		name        string
		jsonIn      string
		fail        bool
		wantConfig  rotang.Configuration
		wantMembers []rotang.Member
	}{
		{
			name:   "simple success",
			jsonIn: jsonRotation,
			wantConfig: rotang.Configuration{
				Config: rotang.Config{
					Description:    "Test description",
					Name:           "Chrome OS Build Sheriff",
					Calendar:       "testCalendarLink@testland.com",
					TokenID:        defaultTokenID,
					DaysToSchedule: 10,
					Owners:         []string{"leowner@google.com"},
					Email: rotang.Email{
						Subject:          "Chrome OS build sheriff reminder",
						Body:             "Some reminder",
						DaysBeforeNotify: 2,
					},
					Shifts: rotang.ShiftConfig{
						StartTime:    mtvMidnight,
						ShiftMembers: 1,
						Length:       5,
						Shifts: []rotang.Shift{
							{
								Name:     "MTV all day",
								Duration: time.Duration(24 * time.Hour),
							},
						},
						Generator: "Legacy",
					},
				},
				Members: []rotang.ShiftMember{
					{
						Email:     "letestbot@google.com",
						ShiftName: "MTV all day",
					},
					{
						Email:     "testsheriff@google.com",
						ShiftName: "MTV all day",
					},
					{
						Email:     "anothersheriff@google.com",
						ShiftName: "MTV all day",
					},
				},
			},
			wantMembers: []rotang.Member{
				{
					Name:  "French Test Bot",
					Email: "letestbot@google.com",
					TZ:    *usLocation,
				},
				{
					Name:  "Test Sheriff",
					Email: "testsheriff@google.com",
					TZ:    *usLocation,
				},
				{
					Name:  "Yet Another Test Sheriff",
					Email: "anothersheriff@google.com",
					TZ:    *usLocation,
				},
			},
		}, {
			name:   "broken JSON",
			jsonIn: `{ "ble }`,
			fail:   true,
		}, {
			name:   "codesearch confirm",
			jsonIn: codesearchRotation,
			wantConfig: rotang.Configuration{
				Config: rotang.Config{
					Description:    "Triage for Codesearch Issues.",
					Name:           "ChOps DevX Codesearch Triage Rotation.",
					Calendar:       "testCalendarLink@testland.com",
					TokenID:        defaultTokenID,
					DaysToSchedule: 10,
					Owners:         []string{"test+one@google.com", "theboss@google.com"},
					Email: rotang.Email{
						Body:             "This is a friendly reminder that you are the Codesearch bug triager for %s. Please do daily bug triage of http://go/cr-cs-triage.",
						Subject:          "ChOps DevX Codesearch Triage reminder",
						DaysBeforeNotify: 2,
					},
					Shifts: rotang.ShiftConfig{
						StartTime:    mtvMidnight,
						ShiftMembers: 1,
						Length:       5,
						Generator:    "Legacy",
						Shifts: []rotang.Shift{
							{
								Name:     "MTV all day",
								Duration: time.Duration(24 * time.Hour),
							},
						},
					},
				},
				Members: []rotang.ShiftMember{
					{
						Email:     "test+one@google.com",
						ShiftName: "MTV all day",
					},
					{
						Email:     "test+two@google.com",
						ShiftName: "MTV all day",
					},
					{
						Email:     "test+three@google.com",
						ShiftName: "MTV all day",
					},
					{
						Email:     "test+four@google.com",
						ShiftName: "MTV all day",
					},
				},
			},
			wantMembers: []rotang.Member{
				{
					Name:  "Test Bot",
					Email: "test+one@google.com",
					TZ:    *euLocation,
				},
				{
					Name:  "Test Sheriff",
					Email: "test+two@google.com",
					TZ:    *euLocation,
				},
				{
					Name:  "Yet Another Test Sheriff",
					Email: "test+three@google.com",
					TZ:    *euLocation,
				},
				{
					Name:  "Another codesearch wiz",
					Email: "test+four@google.com",
					TZ:    *euLocation,
				},
			},
		},
	}

	for _, tst := range tests {
		config, members, err := BuildConfigurationFromJSON([]byte(tst.jsonIn))
		if got, want := (err != nil), tst.fail; got != want {
			t.Errorf("%s: BuildConfigurationFromJSON() = %t want: %t, err: %v", tst.name, got, want, err)
			continue
		}
		if err != nil {
			continue
		}
		if diff := pretty.Compare(config, tst.wantConfig); diff != "" {
			t.Errorf("%s: BuildConfiguration() differs -want +got: \n%s", tst.name, diff)
		}
		if diff := pretty.Compare(members, tst.wantMembers); diff != "" {
			t.Errorf("%s: BuildConfiguration() differs -want +got \n%s", tst.name, diff)
		}
	}
}
