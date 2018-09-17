// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package algo

import (
	"infra/appengine/rotang"
	"sort"
	"time"
)

// Fair implements a rota Generator trying to be fair when scheduling shifts.
type Fair struct {
}

var _ rotang.RotaGenerator = &Fair{}

type fair struct {
	weight int
	member rotang.Member
}

type byFair []*fair

func (b byFair) Less(i, j int) bool {
	if b[i].weight == b[j].weight {
		return b[i].member.Email < b[j].member.Email
	}
	return b[i].weight < b[j].weight
}

func (b byFair) Len() int {
	return len(b)
}

func (b byFair) Swap(i, j int) {
	b[i], b[j] = b[j], b[i]
}

// NewFair returns an instance of the Fair Generator.
func NewFair() *Fair {
	return &Fair{}
}

// Generate generates a rotation using the Fair generator.
// Fair for this Genarator means for a member to not be scheduled for a shift before a member who has not been on shift.
// For members that have all been on shift the Generator uses weights where both how recent a member was on shift and
// number of shifts done by a member is considered. This information is fethed from the provided 'previous' slice.
// If no previous shifts are provided members are selected randomly.
//
// See the tests for further examples of how members are selected.
func (f *Fair) Generate(sc *rotang.Configuration, start time.Time, previous []rotang.ShiftEntry, members []rotang.Member, shiftsToSchedule int) ([]rotang.ShiftEntry, error) {
	if len(previous) < 1 {
		Random(members)
		return MakeShifts(sc, start, HandleShiftMembers(sc, members), shiftsToSchedule), nil
	}

	start = previous[len(previous)-1].EndTime
	membersByShift := HandleShiftMembers(sc, members)
	entriesByShift := HandleShiftEntries(sc, previous)
	for i := range sc.Config.Shifts.Shifts {
		membersByShift[i] = makeFair(membersByShift[i], entriesByShift[i])
	}

	return MakeShifts(sc, start, membersByShift, shiftsToSchedule), nil
}

// Name returns the name of the Generator.
func (f *Fair) Name() string {
	return "Fair"
}

// makeFair sorts the oncall members according to most recent oncall and number of oncall shifts.
func makeFair(members []rotang.Member, previous []rotang.ShiftEntry) []rotang.Member {
	sort.Sort(ByStart(previous))

	oncalls := make(map[string]*fair)
	for _, m := range members {
		oncalls[m.Email] = &fair{
			weight: 1,
			member: m,
		}
	}
	for weight, e := range previous {
		for _, o := range e.OnCall {
			oncalls[o.Email].weight += weight + len(previous)/2
		}
	}
	var fr []*fair
	for _, v := range oncalls {
		fr = append(fr, v)
	}

	sort.Sort(byFair(fr))
	var res []rotang.Member
	for _, m := range fr {
		res = append(res, m.member)
	}
	return res
}
