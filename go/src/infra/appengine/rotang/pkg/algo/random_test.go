// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// See: bugs.chromium.org/p/chromium/issues/detail?id=878462
// +build !386

package algo

import (
	"infra/appengine/rotang"
	"math/rand"
	"testing"
	"time"

	"github.com/kylelemons/godebug/pretty"
)

func TestGenerateFairRandom(t *testing.T) {
	tests := []struct {
		name      string
		fail      bool
		cfg       *rotang.Configuration
		start     time.Time
		members   string
		numShifts int
		previous  string
		want      []rotang.ShiftEntry
	}{{
		name:  "Random when not providing any previous shifts",
		start: midnight,
		cfg: &rotang.Configuration{
			Config: rotang.Config{
				Name: "Test Rota",
				Shifts: rotang.ShiftConfig{
					Length: 5,
					Skip:   2,
					Shifts: []rotang.Shift{
						{
							Name:     "Test Shift",
							Duration: fullDay,
						},
					},
					ShiftMembers: 1,
					Generator:    "Fair",
				},
			},
		},
		members:   "ABCDEFGHIJ",
		numShifts: 4,
		want: []rotang.ShiftEntry{
			{
				Name: "Test Shift",
				OnCall: []rotang.ShiftMember{
					{
						Email:     "I@I.com",
						ShiftName: "Test Shift",
					},
				},
				StartTime: midnight,
				EndTime:   midnight.Add(5 * fullDay),
				Comment:   "",
			}, {
				Name: "Test Shift",
				OnCall: []rotang.ShiftMember{
					{
						Email:     "C@C.com",
						ShiftName: "Test Shift",
					},
				},
				StartTime: midnight.Add(7 * fullDay),
				EndTime:   midnight.Add(7*fullDay + 5*fullDay),
				Comment:   "",
			}, {
				Name: "Test Shift",
				OnCall: []rotang.ShiftMember{
					{
						Email:     "F@F.com",
						ShiftName: "Test Shift",
					},
				},
				StartTime: midnight.Add(14 * fullDay),
				EndTime:   midnight.Add(14*fullDay + 5*fullDay),
				Comment:   "",
			}, {
				Name: "Test Shift",
				OnCall: []rotang.ShiftMember{
					{
						Email:     "A@A.com",
						ShiftName: "Test Shift",
					},
				},
				StartTime: midnight.Add(21 * fullDay),
				EndTime:   midnight.Add(21*fullDay + 5*fullDay),
				Comment:   "",
			},
		},
	},
	}

	// Should give the same pseudo random sequence every time.
	rand.Seed(7357)

	as := New()
	as.Register(NewFair())
	generator, err := as.Fetch("Fair")
	if err != nil {
		t.Fatalf("as.Fetch(%q) failed: %v", "Fair", err)
	}

	for _, tst := range tests {
		tst.cfg.Members = stringToShiftMembers(tst.members, tst.cfg.Config.Shifts.Shifts[0].Name)
		shifts, err := generator.Generate(tst.cfg, tst.start, stringToShifts(tst.previous, tst.cfg.Config.Shifts.Shifts[0].Name), stringToMembers(tst.members, mtvTime), tst.numShifts)
		if got, want := (err != nil), tst.fail; got != want {
			t.Errorf("%s: Generate(_) = %t want: %t, err: %v", tst.name, got, want, err)
			continue
		}
		if err != nil {
			continue
		}
		if diff := pretty.Compare(tst.want, shifts); diff != "" {
			t.Errorf("%s: Generate(_) differs -want +got: %s", tst.name, diff)
		}
	}
}

func TestGenerateRandom(t *testing.T) {
	tests := []struct {
		name      string
		fail      bool
		cfg       *rotang.Configuration
		start     time.Time
		members   string
		numShifts int
		previous  string
		want      []rotang.ShiftEntry
	}{{
		name:  "Random",
		start: midnight,
		cfg: &rotang.Configuration{
			Config: rotang.Config{
				Name: "Test Rota",
				Shifts: rotang.ShiftConfig{
					Length: 5,
					Skip:   2,
					Shifts: []rotang.Shift{
						{
							Name:     "Test Shift",
							Duration: fullDay,
						},
					},
					ShiftMembers: 1,
					Generator:    "Fair",
				},
			},
		},
		members:   "ABCDEFGHIJ",
		numShifts: 4,
		want: []rotang.ShiftEntry{
			{
				Name: "Test Shift",
				OnCall: []rotang.ShiftMember{
					{
						Email:     "I@I.com",
						ShiftName: "Test Shift",
					},
				},
				StartTime: midnight,
				EndTime:   midnight.Add(5 * fullDay),
				Comment:   "",
			}, {
				Name: "Test Shift",
				OnCall: []rotang.ShiftMember{
					{
						Email:     "C@C.com",
						ShiftName: "Test Shift",
					},
				},
				StartTime: midnight.Add(7 * fullDay),
				EndTime:   midnight.Add(7*fullDay + 5*fullDay),
				Comment:   "",
			}, {
				Name: "Test Shift",
				OnCall: []rotang.ShiftMember{
					{
						Email:     "F@F.com",
						ShiftName: "Test Shift",
					},
				},
				StartTime: midnight.Add(14 * fullDay),
				EndTime:   midnight.Add(14*fullDay + 5*fullDay),
				Comment:   "",
			}, {
				Name: "Test Shift",
				OnCall: []rotang.ShiftMember{
					{
						Email:     "A@A.com",
						ShiftName: "Test Shift",
					},
				},
				StartTime: midnight.Add(21 * fullDay),
				EndTime:   midnight.Add(21*fullDay + 5*fullDay),
				Comment:   "",
			},
		}}, {
		name: "Random with previous",
		cfg: &rotang.Configuration{
			Config: rotang.Config{
				Name: "Test Rota",
				Shifts: rotang.ShiftConfig{
					Length: 5,
					Skip:   2,
					Shifts: []rotang.Shift{
						{
							Name:     "Test Shift",
							Duration: time.Hour * 8,
						},
					},
					ShiftMembers: 1,
					Generator:    "Random",
				},
			},
		},
		numShifts: 10,
		members:   "ABCDEF",
		previous:  "ABCDEF",
		want: []rotang.ShiftEntry{
			{
				Name: "Test Shift",
				OnCall: []rotang.ShiftMember{
					{
						Email:     "D@D.com",
						ShiftName: "Test Shift",
					},
				},
				StartTime: midnight,                              // Shift skips two days.
				EndTime:   midnight.Add(4*fullDay + time.Hour*8), // Length of the shift is 5 days.
				Comment:   "",
			}, {
				Name: "Test Shift",
				OnCall: []rotang.ShiftMember{
					{
						Email:     "E@E.com",
						ShiftName: "Test Shift",
					},
				},
				StartTime: midnight.Add(7 * fullDay),
				EndTime:   midnight.Add(6*fullDay + 5*fullDay + time.Hour*8),
				Comment:   "",
			}, {
				Name: "Test Shift",
				OnCall: []rotang.ShiftMember{
					{
						Email:     "F@F.com",
						ShiftName: "Test Shift",
					},
				},
				StartTime: midnight.Add(14 * fullDay),
				EndTime:   midnight.Add(13*fullDay + 5*fullDay + time.Hour*8),
				Comment:   "",
			}, {
				Name: "Test Shift",
				OnCall: []rotang.ShiftMember{
					{
						Email:     "B@B.com",
						ShiftName: "Test Shift",
					},
				},
				StartTime: midnight.Add(21 * fullDay),
				EndTime:   midnight.Add(20*fullDay + 5*fullDay + time.Hour*8),
				Comment:   "",
			}, {
				Name: "Test Shift",
				OnCall: []rotang.ShiftMember{
					{
						Email:     "A@A.com",
						ShiftName: "Test Shift",
					},
				},
				StartTime: midnight.Add(28 * fullDay),
				EndTime:   midnight.Add(27*fullDay + 5*fullDay + time.Hour*8),
				Comment:   "",
			}, {
				Name: "Test Shift",
				OnCall: []rotang.ShiftMember{
					{
						Email:     "C@C.com",
						ShiftName: "Test Shift",
					},
				},
				StartTime: midnight.Add(35 * fullDay),
				EndTime:   midnight.Add(34*fullDay + 5*fullDay + time.Hour*8),
				Comment:   "",
			}, {
				Name: "Test Shift",
				OnCall: []rotang.ShiftMember{
					{
						Email:     "D@D.com",
						ShiftName: "Test Shift",
					},
				},
				StartTime: midnight.Add(42 * fullDay),
				EndTime:   midnight.Add(41*fullDay + 5*fullDay + time.Hour*8),
				Comment:   "",
			}, {
				Name: "Test Shift",
				OnCall: []rotang.ShiftMember{
					{
						Email:     "E@E.com",
						ShiftName: "Test Shift",
					},
				},
				StartTime: midnight.Add(49 * fullDay),
				EndTime:   midnight.Add(48*fullDay + 5*fullDay + time.Hour*8),
				Comment:   "",
			}, {
				Name: "Test Shift",
				OnCall: []rotang.ShiftMember{
					{
						Email:     "F@F.com",
						ShiftName: "Test Shift",
					},
				},
				StartTime: midnight.Add(56 * fullDay),
				EndTime:   midnight.Add(55*fullDay + 5*fullDay + time.Hour*8),
				Comment:   "",
			}, {
				Name: "Test Shift",
				OnCall: []rotang.ShiftMember{
					{
						Email:     "B@B.com",
						ShiftName: "Test Shift",
					},
				},
				StartTime: midnight.Add(63 * fullDay),
				EndTime:   midnight.Add(62*fullDay + 5*fullDay + time.Hour*8),
				Comment:   "",
			},
		},
	},
	}

	rand.Seed(7357)
	as := New()
	as.Register(NewRandomGen())
	generator, err := as.Fetch("Random")
	if err != nil {
		t.Fatalf("as.Fetch(%q) failed: %v", "Random", err)
	}

	for _, tst := range tests {
		tst.cfg.Members = stringToShiftMembers(tst.members, tst.cfg.Config.Shifts.Shifts[0].Name)
		shifts, err := generator.Generate(tst.cfg, tst.start, stringToShifts(tst.previous, tst.cfg.Config.Shifts.Shifts[0].Name), stringToMembers(tst.members, mtvTime), tst.numShifts)
		if got, want := (err != nil), tst.fail; got != want {
			t.Errorf("%s: Generate(_) = %t want: %t, err: %v", tst.name, got, want, err)
		}
		if err != nil {
			continue
		}
		if diff := pretty.Compare(tst.want, shifts); diff != "" {
			t.Errorf("%s: Generate(_) differs -want +got: %s", tst.name, diff)
		}
	}

}
