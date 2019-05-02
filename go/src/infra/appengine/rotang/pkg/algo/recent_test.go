// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package algo

import (
	"infra/appengine/rotang"
	"math/rand"
	"testing"
	"time"

	"github.com/kylelemons/godebug/pretty"
)

func TestMakeRecent(t *testing.T) {

	tests := []struct {
		name    string
		shifts  string
		members string
		want    string
	}{{
		name:    "Simple Cycle",
		shifts:  "ABCDEFGHI",
		members: "ABCDEFGHI",
		want:    "ABCDEFGHI",
	}, {
		name:    "Member not in previous",
		shifts:  "ABCDEGHI",
		members: "ABCDEFGHI",
		want:    "FABCDEGHI",
	}, {
		name:    "Member scheduled multiple times",
		shifts:  "BCDEFGHIAB",
		members: "ABCDEFGHI",
		want:    "CDEFGHIAB",
	}, {
		name:    "Recent vs multiple times",
		shifts:  "ABCDEFGHII",
		members: "ABCDEFGHI",
		want:    "ABCDEFGHI",
	}, {
		name:    "Recent and multiple",
		shifts:  "ABCDEFGHIIA",
		members: "ABCDEFGHI",
		want:    "BCDEFGHIA",
	}, {
		name:    "Recent multiple and not in there",
		shifts:  "ABCDEGCHIJA",
		members: "ABCDEFGHIJ",
		want:    "FBDEGCHIJA",
	}}

	for _, tst := range tests {
		res := makeRecent(stringToMembers(tst.members, mtvTime), stringToShifts(tst.shifts, "MTV all day"))
		if got, want := membersToString(res), tst.want; got != want {
			t.Errorf("%s: makeRecent(_, _ ) = %q want: %q", tst.name, got, want)
		}
	}
}

func TestGenerateRecent(t *testing.T) {
	tests := []struct {
		name      string
		fail      bool
		cfg       *rotang.Configuration
		start     time.Time
		members   string
		numShifts int
		previous  string
		want      []rotang.ShiftEntry
	}{
		{
			name: "Simple cycle",
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
						Generator:    "Recent",
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
							Email:     "A@A.com",
							ShiftName: "Test Shift",
						},
					},
					StartTime: midnight.Add(2 * fullDay),                       // Shift skips two days.
					EndTime:   midnight.Add(fullDay + 5*fullDay + time.Hour*8), // Length of the shift is 5 days.
					Comment:   "",
				}, {
					Name: "Test Shift",
					OnCall: []rotang.ShiftMember{
						{
							Email:     "B@B.com",
							ShiftName: "Test Shift",
						},
					},
					StartTime: midnight.Add(9 * fullDay),
					EndTime:   midnight.Add(8*fullDay + 5*fullDay + time.Hour*8),
					Comment:   "",
				}, {
					Name: "Test Shift",
					OnCall: []rotang.ShiftMember{
						{
							Email:     "C@C.com",
							ShiftName: "Test Shift",
						},
					},
					StartTime: midnight.Add(16 * fullDay),
					EndTime:   midnight.Add(15*fullDay + 5*fullDay + time.Hour*8),
					Comment:   "",
				}, {
					Name: "Test Shift",
					OnCall: []rotang.ShiftMember{
						{
							Email:     "D@D.com",
							ShiftName: "Test Shift",
						},
					},
					StartTime: midnight.Add(23 * fullDay),
					EndTime:   midnight.Add(22*fullDay + 5*fullDay + time.Hour*8),
					Comment:   "",
				}, {
					Name: "Test Shift",
					OnCall: []rotang.ShiftMember{
						{
							Email:     "E@E.com",
							ShiftName: "Test Shift",
						},
					},
					StartTime: midnight.Add(30 * fullDay),
					EndTime:   midnight.Add(29*fullDay + 5*fullDay + time.Hour*8),
					Comment:   "",
				}, {
					Name: "Test Shift",
					OnCall: []rotang.ShiftMember{
						{
							Email:     "F@F.com",
							ShiftName: "Test Shift",
						},
					},
					StartTime: midnight.Add(37 * fullDay),
					EndTime:   midnight.Add(36*fullDay + 5*fullDay + time.Hour*8),
					Comment:   "",
				}, {
					Name: "Test Shift",
					OnCall: []rotang.ShiftMember{
						{
							Email:     "A@A.com",
							ShiftName: "Test Shift",
						},
					},
					StartTime: midnight.Add(44 * fullDay),
					EndTime:   midnight.Add(43*fullDay + 5*fullDay + time.Hour*8),
					Comment:   "",
				}, {
					Name: "Test Shift",
					OnCall: []rotang.ShiftMember{
						{
							Email:     "B@B.com",
							ShiftName: "Test Shift",
						},
					},
					StartTime: midnight.Add(51 * fullDay),
					EndTime:   midnight.Add(50*fullDay + 5*fullDay + time.Hour*8),
					Comment:   "",
				}, {
					Name: "Test Shift",
					OnCall: []rotang.ShiftMember{
						{
							Email:     "C@C.com",
							ShiftName: "Test Shift",
						},
					},
					StartTime: midnight.Add(58 * fullDay),
					EndTime:   midnight.Add(57*fullDay + 5*fullDay + time.Hour*8),
					Comment:   "",
				}, {
					Name: "Test Shift",
					OnCall: []rotang.ShiftMember{
						{
							Email:     "D@D.com",
							ShiftName: "Test Shift",
						},
					},
					StartTime: midnight.Add(65 * fullDay),
					EndTime:   midnight.Add(64*fullDay + 5*fullDay + time.Hour*8),
					Comment:   "",
				},
			},
		},
	}

	// Should give the same pseudo random sequence every time.
	rand.Seed(7357)

	as := New()
	as.Register(NewRecent())
	generator, err := as.Fetch("Recent")
	if err != nil {
		t.Fatalf("as.Fetch(%q) failed: %v", "Recent", err)
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
