// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package algo

import (
	"infra/appengine/rotang"
	"sort"
	"time"
)

// Recent implements a rota Generator considering who was on call most recent.
type Recent struct {
}

var _ rotang.RotaGenerator = &Recent{}

// NewRecent returns an instance of the Recent Generator.
func NewRecent() *Recent {
	return &Recent{}
}

// Generate generates a rotation using the Recent generator.
// The recent generator takes when someone was last on-call into consideration.
//
// See the tests for further examples of how members are selected.
func (r *Recent) Generate(sc *rotang.Configuration, start time.Time, previous []rotang.ShiftEntry, members []rotang.Member, shiftsToSchedule int) ([]rotang.ShiftEntry, error) {
	if len(previous) < 1 {
		Random(members)
		return MakeShifts(sc, start, HandleShiftMembers(sc, members), shiftsToSchedule), nil
	}

	start = previous[len(previous)-1].EndTime
	// Need to add in the skip day(s) when taking in previous shifts.
	start = start.Add(fullDay * time.Duration(sc.Config.Shifts.Skip))
	membersByShift := HandleShiftMembers(sc, members)
	entriesByShift := HandleShiftEntries(sc, previous)
	for i := range sc.Config.Shifts.Shifts {
		membersByShift[i] = makeRecent(membersByShift[i], entriesByShift[i])
	}

	return MakeShifts(sc, start, membersByShift, shiftsToSchedule), nil
}

// Name returns the name of the Generator.
func (r *Recent) Name() string {
	return "Recent"
}

// TZConsider indicates if the generator consideres the TimeZones of members.
func (r *Recent) TZConsider() bool {
	return false
}

func makeRecent(members []rotang.Member, previous []rotang.ShiftEntry) []rotang.Member {
	if len(previous) < 1 {
		return nil
	}
	// Make sure the shifts are sorted by order.
	sort.Sort(sort.Reverse(ByStart(previous)))

	// Set with members already seen.
	seenMembers := make(map[string]struct{})

	oncall := make(map[string]rotang.Member)
	for _, m := range members {
		oncall[m.Email] = m
	}

	var res []rotang.Member
	for _, p := range previous {
		for _, o := range p.OnCall {
			if _, ok := oncall[o.Email]; !ok {
				continue
			}
			if _, ok := seenMembers[o.Email]; ok {
				continue
			}
			res = append([]rotang.Member{oncall[o.Email]}, res...)
			seenMembers[o.Email] = struct{}{}
		}
	}

	var neverOnCall []rotang.Member
	// Order of maps are random in Go.
	// This gives the order of the members never before scheduled will
	// be random.
	for _, m := range oncall {
		if _, ok := seenMembers[m.Email]; ok {
			continue
		}
		neverOnCall = append(neverOnCall, m)
	}

	// Putting the members who was never on-call first in the resulting slice.
	// This gives they'll be scheduled first before the members is res.
	return append(neverOnCall, res...)
}
