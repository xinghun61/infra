// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package algo contains shared functions to be used by rotation Generators.
package algo

import (
	"math/rand"
	"time"

	"infra/appengine/rotang"

	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

var mtvTime = func() *time.Location {
	loc, err := time.LoadLocation("America/Los_Angeles")
	if err != nil {
		panic(err)
	}
	return loc
}()

// Generators contain the currently registered rotation Generators.
type Generators struct {
	registred map[string]rotang.RotaGenerator
}

// New creates a new Generators collection.
func New() *Generators {
	return &Generators{
		registred: make(map[string]rotang.RotaGenerator),
	}
}

// ByStart is used to sort ShiftEntries according to StartTime.
type ByStart []rotang.ShiftEntry

func (b ByStart) Less(i, j int) bool {
	return b[i].StartTime.Before(b[j].StartTime)
}

func (b ByStart) Len() int {
	return len(b)
}

func (b ByStart) Swap(i, j int) {
	b[i], b[j] = b[j], b[i]
}

// Register registers a new rota generator algorithm.
// If another algorithm already exist with the same Name it's overwritten.
func (a *Generators) Register(algo rotang.RotaGenerator) {
	a.registred[algo.Name()] = algo
}

// Fetch fetches the specified generator.
func (a *Generators) Fetch(name string) (rotang.RotaGenerator, error) {
	gen, ok := a.registred[name]
	if !ok {
		return nil, status.Errorf(codes.NotFound, "algorithm: %q not found", name)
	}
	return gen, nil
}

// List returns a list of all registered Generators.
func (a *Generators) List() []string {
	var res []string
	for k := range a.registred {
		res = append(res, k)
	}
	return res
}

const fullDay = 24 * time.Hour

// fixPDTPST handles PST/PDT changes.
// This due to the StartTime read in from the configuration is set to
// PDT.
func fixPDTPST(in time.Time) time.Time {
	z, _ := in.In(mtvTime).Zone()
	if z != "PDT" {
		return in.Add(1 * time.Hour)
	}
	return in
}

// ShiftStartEnd calculates the start and end time of a shift.
func ShiftStartEnd(start time.Time, shiftNumber, shiftIdx int, sc *rotang.ShiftConfig) (time.Time, time.Time) {
	hour, minute, _ := sc.StartTime.Clock()
	year, month, day := start.Date()
	shiftStart := time.Date(year, month, day, hour, minute, 0, 0, time.UTC).Add(time.Duration(shiftNumber) *
		time.Duration(sc.Length+sc.Skip) * fullDay)
	shiftStart = fixPDTPST(shiftStart)
	for i := 0; i < shiftIdx; i++ {
		shiftStart = shiftStart.Add(sc.Shifts[i].Duration)
	}
	shiftEnd := shiftStart.Add(time.Duration(sc.Length) * fullDay)
	shiftEnd = shiftEnd.Add(sc.Shifts[shiftIdx].Duration - fullDay)
	return shiftStart.In(start.Location()), shiftEnd.In(start.Location())
}

// PersonalOutage checks the users OOO entries before scheduling a rotation.
func PersonalOutage(shiftStart time.Time, shiftDays int, shiftDuration time.Duration, member rotang.Member) bool {
	for _, outage := range member.OOO {
		for i := 0; i < shiftDays; i++ {
			todayStart := shiftStart.Add(time.Duration(i) * fullDay)
			todayEnd := todayStart.Add(shiftDuration)
			outageEnd := outage.Start.Add(outage.Duration)
			if todayStart.Before(outageEnd) && (todayEnd.After(outage.Start) || todayEnd.Equal(outage.Start)) {
				return true
			}
		}
	}
	return false
}

// HandleShiftEntries is a helper function to split up a slice of ShiftEntries into a slice for each
// configured shift.
func HandleShiftEntries(sc *rotang.Configuration, shifts []rotang.ShiftEntry) [][]rotang.ShiftEntry {
	shiftMap := make(map[string][]rotang.ShiftEntry)
	for _, se := range shifts {
		shiftMap[se.Name] = append(shiftMap[se.Name], se)
	}
	var res [][]rotang.ShiftEntry
	for _, s := range sc.Config.Shifts.Shifts {
		res = append(res, shiftMap[s.Name])

	}
	return res
}

// HandleShiftMembers builds a slice of shiftmembers for each shift defined in the rotation
// Configuration. Members not in any shift will not be scheduled for oncall rotation.
// This is the format MakeShifts use for membersByShift.
func HandleShiftMembers(sc *rotang.Configuration, cm []rotang.Member) [][]rotang.Member {
	shiftMap := make(map[string][]rotang.Member)
	emailToShift := make(map[string]string)
	for _, sm := range sc.Members {
		emailToShift[sm.Email] = sm.ShiftName
	}
	for _, m := range cm {
		shiftMap[emailToShift[m.Email]] = append(shiftMap[emailToShift[m.Email]], m)
	}
	var res [][]rotang.Member
	for _, s := range sc.Config.Shifts.Shifts {
		res = append(res, shiftMap[s.Name])
	}
	return res
}

// MakeShifts takes a rota configuration and a slice of members. It generates the specified number of
// ShiftEntries using the provided members in order. If the number of shifts to generate is larger than the
// provided list of members the members assigned repeat. The function handles PersonalOutages, skip shifts
// and split shifts.
//
// Eg. Members ["A", "B", "C", "D"] with shiftsToSchedule == 8 -> []rotang.ShiftEntry{"A", "B", "C", "D"}
func MakeShifts(sc *rotang.Configuration, start time.Time, membersByShift [][]rotang.Member, shiftsToSchedule int) []rotang.ShiftEntry {
	var res []rotang.ShiftEntry
	perShiftIdx := make([]int, len(sc.Config.Shifts.Shifts))
	for i := 0; i < shiftsToSchedule; i++ {
		for shiftIdx, shift := range sc.Config.Shifts.Shifts {
			shiftStart, shiftEnd := ShiftStartEnd(start, i, shiftIdx, &sc.Config.Shifts)
			se := rotang.ShiftEntry{
				Name:      shift.Name,
				StartTime: shiftStart,
				EndTime:   shiftEnd,
			}
			if len(membersByShift[shiftIdx]) == 0 {
				res = append(res, se)
				continue
			}
			// With idx: 2 {"A", "B", "C", "D", "E", "F"} -> {"C", "D", "E", "F", "A", "B"}
			shiftMembers := make([]rotang.Member, len(membersByShift[shiftIdx]))
			copy(shiftMembers, membersByShift[shiftIdx])
			shiftMembers = append(shiftMembers[perShiftIdx[shiftIdx]%len(shiftMembers):], shiftMembers[:perShiftIdx[shiftIdx]%len(shiftMembers)]...)
			for oncallIdx := 0; oncallIdx < sc.Config.Shifts.ShiftMembers && len(shiftMembers) > 0; {
				propMember := shiftMembers[0]
				shiftMembers = shiftMembers[1:]
				if PersonalOutage(shiftStart, sc.Config.Shifts.Length, sc.Config.Shifts.Shifts[shiftIdx].Duration, propMember) {
					continue
				}
				se.OnCall = append(se.OnCall, rotang.ShiftMember{
					Email:     propMember.Email,
					ShiftName: shift.Name,
				})
				perShiftIdx[shiftIdx]++
				oncallIdx++
			}
			res = append(res, se)
		}
	}
	return res
}

// Random arranges a slice of members randomly.
func Random(m []rotang.Member) {
	for i := range m {
		swapDest := rand.Int() % len(m)
		m[i], m[swapDest] = m[swapDest], m[i]
	}
}
