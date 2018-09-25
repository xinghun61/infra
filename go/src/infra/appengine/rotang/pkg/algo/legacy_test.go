// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package algo

import (
	"testing"
	"time"

	"infra/appengine/rotang"
	"infra/appengine/rotang/pkg/jsoncfg"

	"github.com/kylelemons/godebug/pretty"
)

var mtvMidnight = func() time.Time {
	t, err := time.Parse(time.RFC822, "02 Jan 06 00:00 PDT")
	if err != nil {
		panic(err)
	}
	return t
}()

const (
	minimalConfig = `
{
  "rotation_config": {
    "calendar_name": "test_test@group.calendar.google.com",
    "event_description": "Build sheriffs for the android platform.",
    "event_title": "Chrome on Android Build Sheriff",
    "people_per_rotation": 1,
    "public_name": "android",
    "reminder_email_body": "This is a friendly reminder that you are currently scheduled as a Chrome on Android build sheriff for %s.",
    "reminder_email_subject": "Chrome on Android build sheriff reminder",
    "rotation_length": 2
  },
  "rotation_list_other": {
    "person": [
      {
        "email_address": "abtest@google.com"
      },
      {
         "email_address": "altest@google.com"
      },
      {
        "email_address": "awtest@google.com"
      }
		]
	}
}`

	usEuOther = `
{
  "rotation_config": {
    "calendar_name": "test_test@group.calendar.google.com",
    "event_description": "Build sheriffs for the android platform.",
    "event_title": "Chrome on Android Build Sheriff",
    "people_per_rotation": 1,
    "public_name": "android",
    "reminder_email_body": "This is a friendly reminder that you are currently scheduled as a Chrome on Android build sheriff for %s.",
    "reminder_email_subject": "Chrome on Android build sheriff reminder",
    "rotation_length": 2
  },
  "rotation_list_other": {
    "person": [
      {
        "email_address": "abtest_other@google.com"
      },
      {
         "email_address": "altest_other@google.com"
      },
      {
        "email_address": "awtest_other@google.com"
      }
		]
	},
  "rotation_list_default": {
    "person": [
      {
        "email_address": "abtest_eu@google.com"
      },
      {
         "email_address": "altest_eu@google.com"
      },
      {
        "email_address": "awtest_eu@google.com"
      }
		]
	},
  "rotation_list_pacific": {
    "person": [
      {
        "email_address": "abtest_us@google.com"
      },
      {
         "email_address": "altest_us@google.com"
      },
      {
        "email_address": "awtest_us@google.com"
      }
		]
	}
}`
)

func buildFromJSON(t *testing.T, json string) (*rotang.Configuration, []rotang.Member) {
	t.Helper()
	r, members, err := jsoncfg.BuildConfigurationFromJSON([]byte(json))
	if err != nil {
		t.Fatalf("jsoncfg.BuildConfigurationFromJSON() failed: %v", err)
	}
	return r, members
}

func TestLegacyWithHistory(t *testing.T) {
	euLocation, err := time.LoadLocation("UTC")
	if err != nil {
		t.Fatalf("time.LoadLocation(%q) failed: %v", "UTC", err)
	}

	cfg, _ := buildFromJSON(t, minimalConfig)

	tests := []struct {
		name      string
		fail      bool
		cfg       *rotang.Configuration
		numShifts int
		members   []rotang.Member
		current   []rotang.ShiftEntry
		want      []rotang.ShiftEntry
	}{{
		name:      "Schedule 4 entries",
		cfg:       cfg,
		numShifts: 4,
		members: []rotang.Member{
			{
				Email: "abtest@google.com",
				TZ:    *euLocation,
			},
			{
				Email: "altest@google.com",
				TZ:    *euLocation,
			},
			{
				Email: "awtest@google.com",
				TZ:    *euLocation,
			},
		},
		current: []rotang.ShiftEntry{
			{
				Name:      "MTV all day",
				StartTime: mtvMidnight,
				EndTime:   mtvMidnight.Add(2 * fullDay),
				OnCall: []rotang.ShiftMember{
					{
						Email:     "abtest@google.com",
						ShiftName: "MTV all day",
					},
				},
			}, {
				Name:      "MTV all day",
				StartTime: mtvMidnight.Add(2 * fullDay),
				EndTime:   mtvMidnight.Add(4 * fullDay),
				OnCall: []rotang.ShiftMember{
					{
						Email:     "altest@google.com",
						ShiftName: "MTV all day",
					},
				},
			}, {
				Name:      "MTV all day",
				StartTime: mtvMidnight.Add(4 * fullDay),
				EndTime:   mtvMidnight.Add(6 * fullDay),
				OnCall: []rotang.ShiftMember{
					{
						Email:     "awtest@google.com",
						ShiftName: "MTV all day",
					},
				},
			}, {
				Name:      "MTV all day",
				StartTime: mtvMidnight.Add(6 * fullDay),
				EndTime:   mtvMidnight.Add(8 * fullDay),
				OnCall: []rotang.ShiftMember{
					{
						Email:     "abtest@google.com",
						ShiftName: "MTV all day",
					},
				},
			},
		},
		want: []rotang.ShiftEntry{
			{
				Name:      "MTV all day",
				StartTime: mtvMidnight.Add(8 * fullDay),
				EndTime:   mtvMidnight.Add(10 * fullDay),
				OnCall: []rotang.ShiftMember{
					{
						Email:     "abtest@google.com",
						ShiftName: "MTV all day",
					},
				},
			}, {
				Name:      "MTV all day",
				StartTime: mtvMidnight.Add(10 * fullDay),
				EndTime:   mtvMidnight.Add(12 * fullDay),
				OnCall: []rotang.ShiftMember{
					{
						Email:     "altest@google.com",
						ShiftName: "MTV all day",
					},
				},
			}, {
				Name:      "MTV all day",
				StartTime: mtvMidnight.Add(12 * fullDay),
				EndTime:   mtvMidnight.Add(14 * fullDay),
				OnCall: []rotang.ShiftMember{
					{
						Email:     "awtest@google.com",
						ShiftName: "MTV all day",
					},
				},
			}, {
				Name:      "MTV all day",
				StartTime: mtvMidnight.Add(14 * fullDay),
				EndTime:   mtvMidnight.Add(16 * fullDay),
				OnCall: []rotang.ShiftMember{
					{
						Email:     "abtest@google.com",
						ShiftName: "MTV all day",
					},
				},
			},
		},
	}}

	l := NewLegacy()

	for _, tst := range tests {
		res, err := l.Generate(tst.cfg, time.Now(), tst.current, tst.members, tst.numShifts)
		if got, want := (err != nil), tst.fail; got != want {
			t.Errorf("%s: Generate() = %t want: %t, err: %v", tst.name, got, want, err)
			continue
		}
		if err != nil {
			continue
		}
		if diff := pretty.Compare(tst.want, res); diff != "" {
			t.Errorf("%s: Generate() differs -want +got: %s", tst.name, diff)
		}
	}
}

func TestLegacyNoHistory(t *testing.T) {
	euLocation, err := time.LoadLocation("UTC")
	if err != nil {
		t.Fatalf("time.LoadLocation(%q) failed: %v", "UTC", err)
	}
	usLocation, err := time.LoadLocation("US/Pacific")
	if err != nil {
		t.Fatalf("time.LoadLocation(%q) failed: %v", "US/Pacific", err)
	}

	cfg, _ := buildFromJSON(t, minimalConfig)
	euOtherCfg, _ := buildFromJSON(t, usEuOther)

	tests := []struct {
		name      string
		fail      bool
		cfg       *rotang.Configuration
		members   []rotang.Member
		numShifts int
		start     time.Time
		want      []rotang.ShiftEntry
	}{
		{
			name:      "Success 4 entries",
			numShifts: 4,
			cfg:       cfg,
			start:     mtvMidnight,
			members: []rotang.Member{
				{
					Email: "abtest@google.com",
					TZ:    *euLocation,
				},
				{
					Email: "altest@google.com",
					TZ:    *euLocation,
				},
				{
					Email: "awtest@google.com",
					TZ:    *euLocation,
				},
			},
			want: []rotang.ShiftEntry{
				{
					Name:      "MTV all day",
					StartTime: mtvMidnight,
					EndTime:   mtvMidnight.Add(2 * fullDay),
					OnCall: []rotang.ShiftMember{
						{
							Email:     "abtest@google.com",
							ShiftName: "MTV all day",
						},
					},
				}, {
					Name:      "MTV all day",
					StartTime: mtvMidnight.Add(2 * fullDay),
					EndTime:   mtvMidnight.Add(4 * fullDay),
					OnCall: []rotang.ShiftMember{
						{
							Email:     "altest@google.com",
							ShiftName: "MTV all day",
						},
					},
				}, {
					Name:      "MTV all day",
					StartTime: mtvMidnight.Add(4 * fullDay),
					EndTime:   mtvMidnight.Add(6 * fullDay),
					OnCall: []rotang.ShiftMember{
						{
							Email:     "awtest@google.com",
							ShiftName: "MTV all day",
						},
					},
				}, {
					Name:      "MTV all day",
					StartTime: mtvMidnight.Add(6 * fullDay),
					EndTime:   mtvMidnight.Add(8 * fullDay),
					OnCall: []rotang.ShiftMember{
						{
							Email:     "abtest@google.com",
							ShiftName: "MTV all day",
						},
					},
				},
			},
		}, {
			name:      "MixedLists",
			numShifts: 10,
			start:     mtvMidnight,
			cfg:       euOtherCfg,
			members: []rotang.Member{
				{
					Email: "abtest_us@google.com",
					TZ:    *usLocation,
				},
				{
					Email: "altest_us@google.com",
					TZ:    *usLocation,
				},
				{
					Email: "awtest_us@google.com",
					TZ:    *usLocation,
				},
				{
					Email: "abtest_eu@google.com",
					TZ:    *euLocation,
				},
				{
					Email: "altest_eu@google.com",
					TZ:    *euLocation,
				},
				{
					Email: "awtest_eu@google.com",
					TZ:    *euLocation,
				},
				{
					Email: "abtest_other@google.com",
					TZ:    *euLocation,
				},
				{
					Email: "altest_other@google.com",
					TZ:    *euLocation,
				},
				{
					Email: "awtest_other@google.com",
					TZ:    *euLocation,
				},
			},
			want: []rotang.ShiftEntry{
				{
					Name:      "MTV all day",
					StartTime: mtvMidnight,
					EndTime:   mtvMidnight.Add(2 * fullDay),
					OnCall: []rotang.ShiftMember{
						{
							Email:     "abtest_us@google.com",
							ShiftName: "MTV all day",
						},
					},
				}, {
					Name:      "MTV all day",
					StartTime: mtvMidnight.Add(2 * fullDay),
					EndTime:   mtvMidnight.Add(4 * fullDay),
					OnCall: []rotang.ShiftMember{
						{
							Email:     "altest_us@google.com",
							ShiftName: "MTV all day",
						},
					},
				}, {
					Name:      "MTV all day",
					StartTime: mtvMidnight.Add(4 * fullDay),
					EndTime:   mtvMidnight.Add(6 * fullDay),
					OnCall: []rotang.ShiftMember{
						{
							Email:     "awtest_us@google.com",
							ShiftName: "MTV all day",
						},
					},
				}, {
					Name:      "MTV all day",
					StartTime: mtvMidnight.Add(6 * fullDay),
					EndTime:   mtvMidnight.Add(8 * fullDay),
					OnCall: []rotang.ShiftMember{
						{
							Email:     "abtest_eu@google.com",
							ShiftName: "MTV all day",
						},
					},
				}, {
					Name:      "MTV all day",
					StartTime: mtvMidnight.Add(8 * fullDay),
					EndTime:   mtvMidnight.Add(10 * fullDay),
					OnCall: []rotang.ShiftMember{
						{
							Email:     "abtest_other@google.com",
							ShiftName: "MTV all day",
						},
					},
				}, {
					Name:      "MTV all day",
					StartTime: mtvMidnight.Add(10 * fullDay),
					EndTime:   mtvMidnight.Add(12 * fullDay),
					OnCall: []rotang.ShiftMember{
						{
							Email:     "altest_eu@google.com",
							ShiftName: "MTV all day",
						},
					},
				}, {
					Name:      "MTV all day",
					StartTime: mtvMidnight.Add(12 * fullDay),
					EndTime:   mtvMidnight.Add(14 * fullDay),
					OnCall: []rotang.ShiftMember{
						{
							Email:     "altest_other@google.com",
							ShiftName: "MTV all day",
						},
					},
				}, {
					Name:      "MTV all day",
					StartTime: mtvMidnight.Add(14 * fullDay),
					EndTime:   mtvMidnight.Add(16 * fullDay),
					OnCall: []rotang.ShiftMember{
						{
							Email:     "awtest_eu@google.com",
							ShiftName: "MTV all day",
						},
					},
				}, {
					Name:      "MTV all day",
					StartTime: mtvMidnight.Add(16 * fullDay),
					EndTime:   mtvMidnight.Add(18 * fullDay),
					OnCall: []rotang.ShiftMember{
						{
							Email:     "awtest_other@google.com",
							ShiftName: "MTV all day",
						},
					},
				}, {
					Name:      "MTV all day",
					StartTime: mtvMidnight.Add(18 * fullDay),
					EndTime:   mtvMidnight.Add(20 * fullDay),
					OnCall: []rotang.ShiftMember{
						{
							Email:     "abtest_us@google.com",
							ShiftName: "MTV all day",
						},
					},
				},
			},
		}, {
			name:      "Split shift",
			start:     mtvMidnight,
			numShifts: 3,
			cfg: &rotang.Configuration{
				Config: rotang.Config{
					Shifts: rotang.ShiftConfig{
						StartTime:    mtvMidnight,
						Length:       2,
						ShiftMembers: 2,
						Shifts: []rotang.Shift{
							{
								Name:     "MTV shift",
								Duration: time.Hour * 12,
							}, {
								Name:     "Other shift",
								Duration: time.Hour * 12,
							},
						},
					},
				},
				Members: []rotang.ShiftMember{
					{
						Email:     "aatest@google.com",
						ShiftName: "MTV shift",
					}, {
						Email:     "bbtest@google.com",
						ShiftName: "MTV shift",
					}, {
						Email:     "cctest@google.com",
						ShiftName: "Other shift",
					}, {
						Email:     "ddtest@google.com",
						ShiftName: "Other shift",
					},
				},
			},
			members: []rotang.Member{
				{
					Email: "aatest@google.com",
					TZ:    *euLocation,
				}, {
					Email: "bbtest@google.com",
					TZ:    *euLocation,
				}, {
					Email: "cctest@google.com",
					TZ:    *euLocation,
				}, {
					Email: "ddtest@google.com",
					TZ:    *euLocation,
				},
			},
			want: []rotang.ShiftEntry{
				{
					Name:      "MTV shift",
					StartTime: mtvMidnight,
					EndTime:   mtvMidnight.Add(fullDay + 12*time.Hour),
					OnCall: []rotang.ShiftMember{
						{
							Email:     "aatest@google.com",
							ShiftName: "MTV shift",
						},
						{
							Email:     "bbtest@google.com",
							ShiftName: "MTV shift",
						},
					},
				}, {
					Name:      "Other shift",
					StartTime: mtvMidnight.Add(12 * time.Hour),
					EndTime:   mtvMidnight.Add(2 * fullDay),
					OnCall: []rotang.ShiftMember{
						{
							Email:     "cctest@google.com",
							ShiftName: "Other shift",
						},
						{
							Email:     "ddtest@google.com",
							ShiftName: "Other shift",
						},
					},
				}, {
					Name:      "MTV shift",
					StartTime: mtvMidnight.Add(2 * fullDay),
					EndTime:   mtvMidnight.Add(3*fullDay + 12*time.Hour),
					OnCall: []rotang.ShiftMember{
						{
							Email:     "aatest@google.com",
							ShiftName: "MTV shift",
						},
						{
							Email:     "bbtest@google.com",
							ShiftName: "MTV shift",
						},
					},
				}, {
					Name:      "Other shift",
					StartTime: mtvMidnight.Add(2*fullDay + 12*time.Hour),
					EndTime:   mtvMidnight.Add(4 * fullDay),
					OnCall: []rotang.ShiftMember{
						{
							Email:     "cctest@google.com",
							ShiftName: "Other shift",
						},
						{
							Email:     "ddtest@google.com",
							ShiftName: "Other shift",
						},
					},
				}, {
					Name:      "MTV shift",
					StartTime: mtvMidnight.Add(4 * fullDay),
					EndTime:   mtvMidnight.Add(5*fullDay + 12*time.Hour),
					OnCall: []rotang.ShiftMember{
						{
							Email:     "aatest@google.com",
							ShiftName: "MTV shift",
						},
						{
							Email:     "bbtest@google.com",
							ShiftName: "MTV shift",
						},
					},
				}, {
					Name:      "Other shift",
					StartTime: mtvMidnight.Add(4*fullDay + 12*time.Hour),
					EndTime:   mtvMidnight.Add(6 * fullDay),
					OnCall: []rotang.ShiftMember{
						{
							Email:     "cctest@google.com",
							ShiftName: "Other shift",
						},
						{
							Email:     "ddtest@google.com",
							ShiftName: "Other shift",
						},
					},
				},
			},
		},
		{
			name:      "Can't schedule members for shift",
			start:     mtvMidnight,
			numShifts: 3,
			members: []rotang.Member{
				{
					Email: "aatest@google.com",
					TZ:    *euLocation,
					OOO: []rotang.OOO{
						{
							Start:    mtvMidnight.Add(4 * time.Hour),
							Duration: 2 * time.Hour,
							Comment:  "OOO - For a few hours.",
						},
					},
				}, {
					Email: "bbtest@google.com",
					TZ:    *euLocation,
					OOO: []rotang.OOO{
						{
							Start:    mtvMidnight.Add(8 * time.Hour),
							Duration: 2 * time.Hour,
							Comment:  "Not during shift",
						}, {
							Start:    mtvMidnight.Add(2*fullDay + 8*time.Hour),
							Duration: 2 * time.Hour,
							Comment:  "Not during shift",
						},
					},
				}, {
					Email: "cctest@google.com",
					TZ:    *euLocation,
					OOO: []rotang.OOO{
						{
							Start:    mtvMidnight.Add(8 * time.Hour),
							Duration: 2 * time.Hour,
							Comment:  "Not during shift",
						}, {
							Start:    mtvMidnight.Add(2*fullDay + 8*time.Hour),
							Duration: 2 * time.Hour,
							Comment:  "Not during shift",
						},
					},
				}, {
					Email: "ddtest@google.com",
					TZ:    *euLocation,
				}, {
					Email: "eetest@google.com",
					TZ:    *euLocation,
				}, {
					Email: "fftest@google.com",
					TZ:    *euLocation,
				},
			},
			cfg: &rotang.Configuration{
				Config: rotang.Config{
					Shifts: rotang.ShiftConfig{
						StartTime:    mtvMidnight,
						Length:       2,
						ShiftMembers: 2,
						Shifts: []rotang.Shift{
							{
								Name:     "MTV shift",
								Duration: time.Hour * 12,
							}, {
								Name:     "Other shift",
								Duration: time.Hour * 12,
							},
						},
					},
				},
				Members: []rotang.ShiftMember{
					{
						Email:     "aatest@google.com",
						ShiftName: "MTV shift",
					}, {
						Email:     "bbtest@google.com",
						ShiftName: "MTV shift",
					}, {
						Email:     "cctest@google.com",
						ShiftName: "MTV shift",
					}, {
						Email:     "ddtest@google.com",
						ShiftName: "Other shift",
					}, {
						Email:     "eetest@google.com",
						ShiftName: "Other shift",
					}, {
						Email:     "fftest@google.com",
						ShiftName: "Other shift",
					},
				},
			},
			want: []rotang.ShiftEntry{
				{
					// All members OOO for this shift.
					Name:      "MTV shift",
					StartTime: mtvMidnight,
					EndTime:   mtvMidnight.Add(fullDay + 12*time.Hour),
				}, {
					Name:      "Other shift",
					StartTime: mtvMidnight.Add(12 * time.Hour),
					EndTime:   mtvMidnight.Add(2 * fullDay),
					OnCall: []rotang.ShiftMember{
						{
							Email:     "ddtest@google.com",
							ShiftName: "Other shift",
						},
						{
							Email:     "eetest@google.com",
							ShiftName: "Other shift",
						},
					},
				}, {
					// bbtest and cctest OOO leaving aatest as the only option.
					Name:      "MTV shift",
					StartTime: mtvMidnight.Add(2 * fullDay),
					EndTime:   mtvMidnight.Add(3*fullDay + 12*time.Hour),
					OnCall: []rotang.ShiftMember{
						{
							Email:     "aatest@google.com",
							ShiftName: "MTV shift",
						},
					},
				}, {
					Name:      "Other shift",
					StartTime: mtvMidnight.Add(2*fullDay + 12*time.Hour),
					EndTime:   mtvMidnight.Add(4 * fullDay),
					OnCall: []rotang.ShiftMember{
						{
							Email:     "fftest@google.com",
							ShiftName: "Other shift",
						},
						{
							Email:     "ddtest@google.com",
							ShiftName: "Other shift",
						},
					},
				}, {
					Name:      "MTV shift",
					StartTime: mtvMidnight.Add(4 * fullDay),
					EndTime:   mtvMidnight.Add(5*fullDay + 12*time.Hour),
					OnCall: []rotang.ShiftMember{
						{
							Email:     "bbtest@google.com",
							ShiftName: "MTV shift",
						},
						{
							Email:     "cctest@google.com",
							ShiftName: "MTV shift",
						},
					},
				}, {
					Name:      "Other shift",
					StartTime: mtvMidnight.Add(4*fullDay + 12*time.Hour),
					EndTime:   mtvMidnight.Add(6 * fullDay),
					OnCall: []rotang.ShiftMember{
						{
							Email:     "eetest@google.com",
							ShiftName: "Other shift",
						},
						{
							Email:     "fftest@google.com",
							ShiftName: "Other shift",
						},
					},
				},
			},
		},
	}

	l := NewLegacy()

	for _, tst := range tests {
		res, err := l.Generate(tst.cfg, tst.start, nil, tst.members, tst.numShifts)
		if got, want := (err != nil), tst.fail; got != want {
			t.Errorf("%s: Generate() = %t want: %t, err: %v", tst.name, got, want, err)
			continue
		}
		if err != nil {
			continue
		}
		if diff := pretty.Compare(tst.want, res); diff != "" {
			t.Errorf("%s: Generate() differs -want +got: %s", tst.name, diff)
		}
	}
}
