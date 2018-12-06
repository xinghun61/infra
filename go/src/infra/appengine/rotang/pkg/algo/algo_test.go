// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package algo

import (
	"infra/appengine/rotang"
	"sort"
	"strings"
	"testing"
	"time"

	"github.com/kylelemons/godebug/pretty"
)

type testGenerator struct {
	name string
}

func (t *testGenerator) Name() string {
	return t.name
}

func (t *testGenerator) Generate(_ *rotang.Configuration, _ time.Time, _ []rotang.ShiftEntry, _ []rotang.Member, _ int) ([]rotang.ShiftEntry, error) {
	return nil, nil
}

var _ rotang.RotaGenerator = &testGenerator{}

func stringToGenerators(in string) []rotang.RotaGenerator {
	var res []rotang.RotaGenerator
	for _, c := range in {
		res = append(res, &testGenerator{
			name: string(c),
		})
	}
	return res
}

func TestShiftStartEnd(t *testing.T) {
	tests := []struct {
		name        string
		cfg         *rotang.ShiftConfig
		start       time.Time
		shiftNumber int
		shiftIdx    int
		shifts      int
	}{{
		name:   "First try",
		start:  midnight,
		shifts: 20,
		cfg: &rotang.ShiftConfig{
			StartTime: midnight,
			Length:    5,
			Skip:      2,
			Shifts: []rotang.Shift{
				{
					Name:     "MTV all day",
					Duration: 24 * time.Hour,
				},
			},
		},
	},
	}

	for _, tst := range tests {
		for i := 0; i < tst.shifts; i++ {
			start, end := ShiftStartEnd(tst.start, i, tst.shiftIdx, tst.cfg)
			t.Logf("start: %v, end: %v", start, end)
		}
	}
}

func TestRegisterList(t *testing.T) {
	tests := []struct {
		name       string
		generators string
		want       string
	}{
		{
			name:       "Single gen",
			generators: "A",
			want:       "A",
		}, {
			name:       "A few generators",
			generators: "ABCDEF",
			want:       "ABCDEF",
		}, {
			name:       "Duplicate generator",
			generators: "ABBA",
			want:       "AB",
		},
	}

	for _, tst := range tests {
		a := New()
		for _, g := range stringToGenerators(tst.generators) {
			a.Register(g)
		}
		got := []byte(strings.Join(a.List(), ""))
		want := []byte(tst.want)
		sort.Slice(got, func(i, j int) bool {
			return got[i] < got[j]
		})
		sort.Slice(want, func(i, j int) bool {
			return want[i] < want[j]
		})

		if diff := pretty.Compare(want, got); diff != "" {
			t.Errorf("%s: a.List() differs -want +got:\n %s", tst.name, diff)
		}
	}
}

func TestFetch(t *testing.T) {
	tests := []struct {
		name       string
		fail       bool
		generators string
		fetch      string
	}{
		{
			name:       "Success fetch",
			generators: "A",
			fetch:      "A",
		}, {
			name:       "Generator not exists",
			fail:       true,
			generators: "ACD",
			fetch:      "B",
		}, {
			name:       "Multiple generators",
			generators: "ABCDEFGHI",
			fetch:      "E",
		},
	}

	for _, tst := range tests {
		a := New()
		for _, g := range stringToGenerators(tst.generators) {
			a.Register(g)
		}
		_, err := a.Fetch(tst.fetch)
		if got, want := (err != nil), tst.fail; got != want {
			t.Errorf("%s: a.Fetch(%q) = %t want: %t, err: %v", tst.name, tst.fetch, got, want, err)
		}
	}
}

func TestHandleShiftEntries(t *testing.T) {
	tests := []struct {
		name   string
		cfg    *rotang.Configuration
		shifts []rotang.ShiftEntry
		want   [][]rotang.ShiftEntry
	}{{
		name: "Single shift",
		cfg: &rotang.Configuration{
			Config: rotang.Config{
				Description: "Test",
				Name:        "test rota",
				Shifts: rotang.ShiftConfig{
					StartTime:    midnight,
					ShiftMembers: 1,
					Length:       2,
					Shifts: []rotang.Shift{
						{
							Name:     "MTV Shift",
							Duration: 24 * time.Hour,
						},
					},
				},
			},
		},
		shifts: []rotang.ShiftEntry{
			{
				Name:      "MTV Shift",
				StartTime: midnight,
				EndTime:   midnight.Add(2 * 24 * time.Hour),
			},
			{
				Name:      "MTV Shift",
				StartTime: midnight.Add(2 * 24 * time.Hour),
				EndTime:   midnight.Add(4 * 24 * time.Hour),
			},
		},
		want: [][]rotang.ShiftEntry{
			{
				{
					Name:      "MTV Shift",
					StartTime: midnight,
					EndTime:   midnight.Add(2 * 24 * time.Hour),
				},
				{
					Name:      "MTV Shift",
					StartTime: midnight.Add(2 * 24 * time.Hour),
					EndTime:   midnight.Add(4 * 24 * time.Hour),
				},
			},
		},
	},
	}

	for _, tst := range tests {
		got := HandleShiftEntries(tst.cfg, tst.shifts)
		if diff := pretty.Compare(tst.want, got); diff != "" {
			t.Errorf("%s: HandleShiftEntries(_, _) differs -want +got, %s", tst.name, diff)
		}
	}
}

func TestHandleShiftMembers(t *testing.T) {
	tests := []struct {
		name       string
		cfg        *rotang.Configuration
		memberPool []rotang.Member
		want       [][]rotang.Member
	}{{
		name: "Multiple shifts",
		cfg: &rotang.Configuration{
			Config: rotang.Config{
				Description: "Test",
				Name:        "test rota",
				Shifts: rotang.ShiftConfig{
					StartTime:    midnight,
					ShiftMembers: 1,
					Length:       2,
					Shifts: []rotang.Shift{
						{
							Name:     "MTV Shift",
							Duration: 8 * time.Hour,
						},
						{
							Name: "SYD Shift",

							Duration: 8 * time.Hour,
						},
						{
							Name:     "EU Shift",
							Duration: 8 * time.Hour,
						},
					},
				},
			},
			Members: []rotang.ShiftMember{
				{
					Email:     "mtv1@oncall.com",
					ShiftName: "MTV Shift",
				},
				{
					Email:     "mtv2@oncall.com",
					ShiftName: "MTV Shift",
				},
				{
					Email:     "mtv3@oncall.com",
					ShiftName: "MTV Shift",
				},
				{
					Email:     "mtv4@oncall.com",
					ShiftName: "MTV Shift",
				},
				{
					Email:     "syd1@oncall.com",
					ShiftName: "SYD Shift",
				},
				{
					Email:     "syd2@oncall.com",
					ShiftName: "SYD Shift",
				},
				{
					Email:     "syd3@oncall.com",
					ShiftName: "SYD Shift",
				},
				{
					Email:     "eu1@oncall.com",
					ShiftName: "EU Shift",
				},
				{
					Email:     "eu2@oncall.com",
					ShiftName: "EU Shift",
				},
			},
		},
		memberPool: []rotang.Member{
			{
				Email: "mtv1@oncall.com",
			},
			{
				Email: "mtv2@oncall.com",
			},
			{
				Email: "mtv3@oncall.com",
			},
			{
				Email: "mtv4@oncall.com",
			},
			{
				Email: "syd1@oncall.com",
			},
			{
				Email: "syd2@oncall.com",
			},
			{
				Email: "syd3@oncall.com",
			},
			{
				Email: "eu1@oncall.com",
			},
			{
				Email: "eu2@oncall.com",
			},
		},
		want: [][]rotang.Member{
			{
				{
					Email: "mtv1@oncall.com",
				},
				{
					Email: "mtv2@oncall.com",
				},
				{
					Email: "mtv3@oncall.com",
				},
				{
					Email: "mtv4@oncall.com",
				},
			}, {
				{
					Email: "syd1@oncall.com",
				},
				{
					Email: "syd2@oncall.com",
				},
				{
					Email: "syd3@oncall.com",
				},
			}, {
				{
					Email: "eu1@oncall.com",
				},
				{
					Email: "eu2@oncall.com",
				},
			},
		},
	}, {
		name: "User with no shift",
		cfg: &rotang.Configuration{
			Config: rotang.Config{
				Description: "Test",
				Name:        "test rota",
				Shifts: rotang.ShiftConfig{
					StartTime:    midnight,
					ShiftMembers: 1,
					Length:       2,
					Shifts: []rotang.Shift{
						{
							Name:     "MTV Shift",
							Duration: 8 * time.Hour,
						},
						{
							Name:     "SYD Shift",
							Duration: 8 * time.Hour,
						},
						{
							Name:     "EU Shift",
							Duration: 8 * time.Hour,
						},
					},
				},
			},
			Members: []rotang.ShiftMember{
				{
					Email:     "mtv1@oncall.com",
					ShiftName: "MTV Shift",
				},
				{
					Email:     "mtv2@oncall.com",
					ShiftName: "MTV Shift",
				},
				{
					Email:     "mtv3@oncall.com",
					ShiftName: "MTV Shift",
				},
				{
					Email:     "mtv4@oncall.com",
					ShiftName: "MTV Shift",
				},
				{
					Email:     "syd1@oncall.com",
					ShiftName: "SYD Shift",
				},
				{
					Email:     "syd2@oncall.com",
					ShiftName: "SYD Shift",
				},
				{
					Email: "syd3@oncall.com",
				},
				{
					Email:     "eu1@oncall.com",
					ShiftName: "EU Shift",
				},
				{
					Email:     "eu2@oncall.com",
					ShiftName: "EU Shift",
				},
			},
		},
		memberPool: []rotang.Member{
			{
				Email: "mtv1@oncall.com",
			},
			{
				Email: "mtv2@oncall.com",
			},
			{
				Email: "mtv3@oncall.com",
			},
			{
				Email: "mtv4@oncall.com",
			},
			{
				Email: "syd1@oncall.com",
			},
			{
				Email: "syd2@oncall.com",
			},
			{
				Email: "syd3@oncall.com",
			},
			{
				Email: "eu1@oncall.com",
			},
			{
				Email: "eu2@oncall.com",
			},
		},
		want: [][]rotang.Member{
			{
				{
					Email: "mtv1@oncall.com",
				},
				{
					Email: "mtv2@oncall.com",
				},
				{
					Email: "mtv3@oncall.com",
				},
				{
					Email: "mtv4@oncall.com",
				},
			}, {
				{
					Email: "syd1@oncall.com",
				},
				{
					Email: "syd2@oncall.com",
				},
			}, {
				{
					Email: "eu1@oncall.com",
				},
				{
					Email: "eu2@oncall.com",
				},
			},
		},
	}, {
		name: "Shift with no users",
		cfg: &rotang.Configuration{
			Config: rotang.Config{
				Description: "Test",
				Name:        "test rota",
				Shifts: rotang.ShiftConfig{
					StartTime:    midnight,
					ShiftMembers: 1,
					Length:       2,
					Shifts: []rotang.Shift{
						{
							Name:     "MTV Shift",
							Duration: 6 * time.Hour,
						},
						{
							Name:     "Out of MTV office hours",
							Duration: 6 * time.Hour,
						},
						{
							Name:     "SYD Shift",
							Duration: 6 * time.Hour,
						},
						{
							Name:     "Out of SYD office hours",
							Duration: 6 * time.Hour,
						},
					},
				},
			},
			Members: []rotang.ShiftMember{
				{
					Email:     "mtv1@oncall.com",
					ShiftName: "MTV Shift",
				},
				{
					Email:     "mtv2@oncall.com",
					ShiftName: "MTV Shift",
				},
				{
					Email:     "mtv3@oncall.com",
					ShiftName: "MTV Shift",
				},
				{
					Email:     "mtv4@oncall.com",
					ShiftName: "MTV Shift",
				},
				{
					Email:     "syd1@oncall.com",
					ShiftName: "SYD Shift",
				},
				{
					Email:     "syd2@oncall.com",
					ShiftName: "SYD Shift",
				},
				{
					Email: "syd3@oncall.com",
				},
			},
		},
		memberPool: []rotang.Member{
			{
				Email: "mtv1@oncall.com",
			},
			{
				Email: "mtv2@oncall.com",
			},
			{
				Email: "mtv3@oncall.com",
			},
			{
				Email: "mtv4@oncall.com",
			},
			{
				Email: "syd1@oncall.com",
			},
			{
				Email: "syd2@oncall.com",
			},
			{
				Email: "syd3@oncall.com",
			},
		},
		want: [][]rotang.Member{
			{
				{
					Email: "mtv1@oncall.com",
				},
				{
					Email: "mtv2@oncall.com",
				},
				{
					Email: "mtv3@oncall.com",
				},
				{
					Email: "mtv4@oncall.com",
				},
			}, {}, {
				{
					Email: "syd1@oncall.com",
				},
				{
					Email: "syd2@oncall.com",
				},
			}, {},
		},
	},
	}

	for _, tst := range tests {
		got := HandleShiftMembers(tst.cfg, tst.memberPool)
		if diff := pretty.Compare(tst.want, got); diff != "" {
			t.Errorf("%s: handleShiftMember(_, _) differs -want +got, %s", tst.name, diff)
		}
	}
}

func TestPersonalOutage(t *testing.T) {
	timeFormat := "2006-01-02 15:04:05 -0700 MST"
	start, err := time.Parse(timeFormat, "2018-12-21 08:00:00 +0000 UTC")
	if err != nil {
		t.Fatalf("time.Parse() failed: %v", err)
	}
	end, err := time.Parse(timeFormat, "2019-09-17 08:00:00 +0000 UTC")
	if err != nil {
		t.Fatalf("time.Parse() failed: %v", err)
	}

	tests := []struct {
		name     string
		start    time.Time
		days     int
		duration time.Duration
		member   *rotang.Member
		want     bool
	}{{
		name:     "olakar@google.com irl",
		want:     true,
		duration: fullDay,
		member: &rotang.Member{
			Name:  "Ola Karlsson",
			Email: "olakar@google.com",
			OOO: []rotang.OOO{
				{
					Start:    start,
					Duration: end.Sub(start),
					Comment:  "Something",
				},
			},
		},
	}, {
		name:     "Outage after shift",
		duration: fullDay,
		member: &rotang.Member{
			Name:  "Ola Karlsson",
			Email: "olakar@google.com",
			OOO: []rotang.OOO{
				{
					Start:    start.Add(6 * fullDay),
					Duration: end.Sub(start),
					Comment:  "Something",
				},
			},
		},
	}, {
		name:     "Outage between shifts",
		duration: 12 * time.Hour,
		member: &rotang.Member{
			Name:  "Ola Karlsson",
			Email: "olakar@google.com",
			OOO: []rotang.OOO{
				{
					Start:    start.Add(14 * time.Hour),
					Duration: 6 * time.Hour,
					Comment:  "Something",
				},
			},
		},
	}, {
		name:     "Outage inside single shift",
		want:     true,
		duration: 12 * time.Hour,
		member: &rotang.Member{
			Name:  "Ola Karlsson",
			Email: "olakar@google.com",
			OOO: []rotang.OOO{
				{
					Start:    start.Add(4 * time.Hour),
					Duration: 6 * time.Hour,
					Comment:  "Something",
				},
			},
		},
	},
	}

	for _, tst := range tests {
		res := PersonalOutage(start.Add(-4*fullDay), 5, tst.duration, *tst.member)
		if got, want := res, tst.want; got != want {
			t.Errorf("%s: PersonalOutage() = %t, want: %t", tst.name, got, want)
		}
	}
}

func TestMakeShifts(t *testing.T) {
	tests := []struct {
		name       string
		cfg        *rotang.Configuration
		schedule   int
		start      time.Time
		memberPool []rotang.Member
		want       []rotang.ShiftEntry
	}{{
		name:     "More than 2 shifts",
		schedule: 2,
		start:    midnight.Add(12 * time.Hour),
		cfg: &rotang.Configuration{
			Config: rotang.Config{
				Description: "Test",
				Name:        "test rota",
				Shifts: rotang.ShiftConfig{
					StartTime:    midnight,
					ShiftMembers: 1,
					Length:       2,
					Shifts: []rotang.Shift{
						{
							Name:     "MTV Shift",
							Duration: 8 * time.Hour,
						},
						{
							Name:     "SYD Shift",
							Duration: 8 * time.Hour,
						},
						{
							Name:     "EU Shift",
							Duration: 8 * time.Hour,
						},
					},
				},
			},
			Members: []rotang.ShiftMember{
				{
					Email:     "mtv@oncall.com",
					ShiftName: "MTV Shift",
				},
				{
					Email:     "syd@oncall.com",
					ShiftName: "SYD Shift",
				},
				{
					Email:     "eu@oncall.com",
					ShiftName: "EU Shift",
				},
			},
		},
		memberPool: []rotang.Member{
			{
				Email: "mtv@oncall.com",
			},
			{
				Email: "syd@oncall.com",
			},
			{
				Email: "eu@oncall.com",
			},
		},
		want: []rotang.ShiftEntry{
			{
				Name:      "MTV Shift",
				StartTime: midnight,
				EndTime:   midnight.Add(fullDay + 8*time.Hour),
				OnCall: []rotang.ShiftMember{
					{
						Email:     "mtv@oncall.com",
						ShiftName: "MTV Shift",
					},
				},
			},
			{
				Name:      "SYD Shift",
				StartTime: midnight.Add(8 * time.Hour),
				EndTime:   midnight.Add(fullDay + 16*time.Hour),
				OnCall: []rotang.ShiftMember{
					{
						Email:     "syd@oncall.com",
						ShiftName: "SYD Shift",
					},
				},
			},
			{
				Name:      "EU Shift",
				StartTime: midnight.Add(2 * 8 * time.Hour),
				EndTime:   midnight.Add(fullDay + 24*time.Hour),
				OnCall: []rotang.ShiftMember{
					{
						Email:     "eu@oncall.com",
						ShiftName: "EU Shift",
					},
				},
			},
			{
				Name:      "MTV Shift",
				StartTime: midnight.Add(2 * fullDay),
				EndTime:   midnight.Add(3*fullDay + 8*time.Hour),
				OnCall: []rotang.ShiftMember{
					{
						Email:     "mtv@oncall.com",
						ShiftName: "MTV Shift",
					},
				},
			},
			{
				Name:      "SYD Shift",
				StartTime: midnight.Add(8*time.Hour + 2*fullDay),
				EndTime:   midnight.Add(3*fullDay + 16*time.Hour),
				OnCall: []rotang.ShiftMember{
					{
						Email:     "syd@oncall.com",
						ShiftName: "SYD Shift",
					},
				},
			},
			{
				Name:      "EU Shift",
				StartTime: midnight.Add(16*time.Hour + 2*fullDay),
				EndTime:   midnight.Add(3*fullDay + 24*time.Hour),
				OnCall: []rotang.ShiftMember{
					{
						Email:     "eu@oncall.com",
						ShiftName: "EU Shift",
					},
				},
			},
		},
	}, {
		name:     "Different duration shifts",
		schedule: 2,
		start:    midnight.Add(12 * time.Hour),
		cfg: &rotang.Configuration{
			Config: rotang.Config{
				Description: "Test",
				Name:        "test rota",
				Shifts: rotang.ShiftConfig{
					StartTime:    midnight,
					ShiftMembers: 1,
					Length:       2,
					Shifts: []rotang.Shift{
						{
							Name:     "MTV Shift",
							Duration: 6 * time.Hour,
						},
						{
							Name:     "SYD Shift",
							Duration: 6 * time.Hour,
						},
						{
							Name:     "EU Shift",
							Duration: 12 * time.Hour,
						},
					},
				},
			},
			Members: []rotang.ShiftMember{
				{
					Email:     "mtv@oncall.com",
					ShiftName: "MTV Shift",
				},
				{
					Email:     "syd@oncall.com",
					ShiftName: "SYD Shift",
				},
				{
					Email:     "eu@oncall.com",
					ShiftName: "EU Shift",
				},
			},
		},
		memberPool: []rotang.Member{
			{
				Email: "mtv@oncall.com",
			},
			{
				Email: "syd@oncall.com",
			},
			{
				Email: "eu@oncall.com",
			},
		},
		want: []rotang.ShiftEntry{
			{
				Name:      "MTV Shift",
				StartTime: midnight,
				EndTime:   midnight.Add(fullDay + 6*time.Hour),
				OnCall: []rotang.ShiftMember{
					{
						Email:     "mtv@oncall.com",
						ShiftName: "MTV Shift",
					},
				},
			},
			{
				Name:      "SYD Shift",
				StartTime: midnight.Add(6 * time.Hour),
				EndTime:   midnight.Add(fullDay + 12*time.Hour),
				OnCall: []rotang.ShiftMember{
					{
						Email:     "syd@oncall.com",
						ShiftName: "SYD Shift",
					},
				},
			},
			{
				Name:      "EU Shift",
				StartTime: midnight.Add(12 * time.Hour),
				EndTime:   midnight.Add(fullDay + 24*time.Hour),
				OnCall: []rotang.ShiftMember{
					{
						Email:     "eu@oncall.com",
						ShiftName: "EU Shift",
					},
				},
			},
			{
				Name:      "MTV Shift",
				StartTime: midnight.Add(2 * fullDay),
				EndTime:   midnight.Add(3*fullDay + 6*time.Hour),
				OnCall: []rotang.ShiftMember{
					{
						Email:     "mtv@oncall.com",
						ShiftName: "MTV Shift",
					},
				},
			},
			{
				Name:      "SYD Shift",
				StartTime: midnight.Add(6*time.Hour + 2*fullDay),
				EndTime:   midnight.Add(3*fullDay + 12*time.Hour),
				OnCall: []rotang.ShiftMember{
					{
						Email:     "syd@oncall.com",
						ShiftName: "SYD Shift",
					},
				},
			},
			{
				Name:      "EU Shift",
				StartTime: midnight.Add(12*time.Hour + 2*fullDay),
				EndTime:   midnight.Add(3*fullDay + 24*time.Hour),
				OnCall: []rotang.ShiftMember{
					{
						Email:     "eu@oncall.com",
						ShiftName: "EU Shift",
					},
				},
			},
		},
	}, {
		name:     "Put members in the right shift",
		schedule: 2,
		start:    midnight.Add(12 * time.Hour),
		cfg: &rotang.Configuration{
			Config: rotang.Config{
				Description: "Test",
				Name:        "test rota",
				Shifts: rotang.ShiftConfig{
					StartTime:    midnight,
					ShiftMembers: 2,
					Length:       2,
					Shifts: []rotang.Shift{
						{
							Name:     "MTV Shift",
							Duration: 8 * time.Hour,
						},
						{
							Name:     "SYD Shift",
							Duration: 8 * time.Hour,
						},
						{
							Name:     "EU Shift",
							Duration: 8 * time.Hour,
						},
					},
				},
			},
			Members: []rotang.ShiftMember{
				{
					Email:     "mtv1@oncall.com",
					ShiftName: "MTV Shift",
				},
				{
					Email:     "mtv2@oncall.com",
					ShiftName: "MTV Shift",
				},
				{
					Email:     "mtv3@oncall.com",
					ShiftName: "MTV Shift",
				},
				{
					Email:     "mtv4@oncall.com",
					ShiftName: "MTV Shift",
				},
				{
					Email:     "syd1@oncall.com",
					ShiftName: "SYD Shift",
				},
				{
					Email:     "syd2@oncall.com",
					ShiftName: "SYD Shift",
				},
				{
					Email:     "syd3@oncall.com",
					ShiftName: "SYD Shift",
				},
				{
					Email:     "eu1@oncall.com",
					ShiftName: "EU Shift",
				},
				{
					Email:     "eu2@oncall.com",
					ShiftName: "EU Shift",
				},
			},
		},
		memberPool: []rotang.Member{
			{
				Email: "mtv1@oncall.com",
			},
			{
				Email: "mtv2@oncall.com",
			},
			{
				Email: "mtv3@oncall.com",
			},
			{
				Email: "mtv4@oncall.com",
			},
			{
				Email: "syd1@oncall.com",
			},
			{
				Email: "syd2@oncall.com",
			},
			{
				Email: "syd3@oncall.com",
			},
			{
				Email: "eu1@oncall.com",
			},
			{
				Email: "eu2@oncall.com",
			},
		},
		want: []rotang.ShiftEntry{
			{
				Name:      "MTV Shift",
				StartTime: midnight,
				EndTime:   midnight.Add(fullDay + 8*time.Hour),
				OnCall: []rotang.ShiftMember{
					{
						Email:     "mtv1@oncall.com",
						ShiftName: "MTV Shift",
					},
					{
						Email:     "mtv2@oncall.com",
						ShiftName: "MTV Shift",
					},
				},
			},
			{
				Name:      "SYD Shift",
				StartTime: midnight.Add(8 * time.Hour),
				EndTime:   midnight.Add(fullDay + 16*time.Hour),
				OnCall: []rotang.ShiftMember{
					{
						Email:     "syd1@oncall.com",
						ShiftName: "SYD Shift",
					},
					{
						Email:     "syd2@oncall.com",
						ShiftName: "SYD Shift",
					},
				},
			},
			{
				Name:      "EU Shift",
				StartTime: midnight.Add(2 * 8 * time.Hour),
				EndTime:   midnight.Add(fullDay + 24*time.Hour),
				OnCall: []rotang.ShiftMember{
					{
						Email:     "eu1@oncall.com",
						ShiftName: "EU Shift",
					},
					{
						Email:     "eu2@oncall.com",
						ShiftName: "EU Shift",
					},
				},
			},
			{
				Name:      "MTV Shift",
				StartTime: midnight.Add(2 * fullDay),
				EndTime:   midnight.Add(3*fullDay + 8*time.Hour),
				OnCall: []rotang.ShiftMember{
					{
						Email:     "mtv3@oncall.com",
						ShiftName: "MTV Shift",
					},
					{
						Email:     "mtv4@oncall.com",
						ShiftName: "MTV Shift",
					},
				},
			},
			{
				Name:      "SYD Shift",
				StartTime: midnight.Add(8*time.Hour + 2*fullDay),
				EndTime:   midnight.Add(3*fullDay + 16*time.Hour),
				OnCall: []rotang.ShiftMember{
					{
						Email:     "syd3@oncall.com",
						ShiftName: "SYD Shift",
					},
					{
						Email:     "syd1@oncall.com",
						ShiftName: "SYD Shift",
					},
				},
			},
			{
				Name:      "EU Shift",
				StartTime: midnight.Add(16*time.Hour + 2*fullDay),
				EndTime:   midnight.Add(3*fullDay + 24*time.Hour),
				OnCall: []rotang.ShiftMember{
					{
						Email:     "eu1@oncall.com",
						ShiftName: "EU Shift",
					},
					{
						Email:     "eu2@oncall.com",
						ShiftName: "EU Shift",
					},
				},
			},
		},
	},
	}

	for _, tst := range tests {
		got := MakeShifts(tst.cfg, tst.start, HandleShiftMembers(tst.cfg, tst.memberPool), tst.schedule)
		if diff := pretty.Compare(tst.want, got); diff != "" {
			t.Errorf("%s: MakeShifts(_, %v, _, %d) differ: -want +got, %s", tst.name, tst.start, tst.schedule, diff)
		}
	}
}
