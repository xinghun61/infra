// Package algo contains shared functions to be used by rotation Generators.
package algo

import (
	"infra/appengine/rotang"
	"math/rand"
	"time"

	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

// Algos contain the currently registered rotation Generators.
type Algos struct {
	registred map[string]rotang.RotaGenerator
}

// New creates a new Algo collection.
func New() *Algos {
	return &Algos{
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
func (a *Algos) Register(algo rotang.RotaGenerator) {
	a.registred[algo.Name()] = algo
}

// Fetch fetches the specified generator.
func (a *Algos) Fetch(name string) (rotang.RotaGenerator, error) {
	gen, ok := a.registred[name]
	if !ok {
		return nil, status.Errorf(codes.NotFound, "algorithm: %q not found", name)
	}
	return gen, nil
}

// List returns a list of all registered Generators.
func (a *Algos) List() []string {
	var res []string
	for k := range a.registred {
		res = append(res, k)
	}
	return res
}

const fullDay = 24 * time.Hour

// ShiftStartEnd calculates the start and end time of a shift.
func ShiftStartEnd(start time.Time, shiftNumber, shiftIdx int, sc *rotang.ShiftConfig) (time.Time, time.Time) {
	hour, minute, _ := sc.StartTime.UTC().Clock()
	year, month, day := start.UTC().Date()
	shiftStart := time.Date(year, month, day, hour, minute, 0, 0, time.UTC).Add(time.Duration(shiftNumber) *
		time.Duration(sc.Length+sc.Skip) * fullDay)
	if shiftIdx > 0 && shiftIdx < len(sc.Shifts) {
		shiftStart = shiftStart.Add(sc.Shifts[shiftIdx].Duration)
	}
	shiftEnd := shiftStart.Add(time.Duration(sc.Length) * fullDay)
	return shiftStart.In(start.Location()), shiftEnd.In(start.Location())
}

// PersonalOutage checks the users OOO entries before scheduling a rotation.
func PersonalOutage(shiftStart time.Time, shiftDays int, shiftDuration time.Duration, member rotang.Member) bool {
	for _, outage := range member.OOO {
		for i := 0; i < shiftDays; i++ {
			todayStart := shiftStart.Add(time.Duration(i) * fullDay)
			todayEnd := todayStart.Add(shiftDuration)
			outageEnd := outage.Start.Add(outage.Duration)
			if outage.Start.After(todayStart) && outage.Start.Before(todayEnd) ||
				outageEnd.Before(todayEnd) && outageEnd.After(todayStart) {
				return true
			}
		}
	}
	return false
}

// MakeShifts takes a rota configuration and a slice of members. It generates the specified number of
// ShiftEntries using the provided members in order. If the number of shifts to generate is larger than the
// provided list of members the members assigned repeat. The function handles PersonalOutages, skip shifts
// and split shifts.
//
// Eg. Members ["A", "B", "C", "D"] with shiftsToSchedule == 8 -> []rotang.ShiftEntry{"A", "B", "C", "D"}
func MakeShifts(sc *rotang.Configuration, start time.Time, cm []rotang.Member, shiftsToSchedule int) []rotang.ShiftEntry {
	var res []rotang.ShiftEntry
	for i, j := 0, 0; i < shiftsToSchedule; i++ {
		for shiftIdx, shift := range sc.Config.Shifts.Shifts {
			shiftStart, shiftEnd := ShiftStartEnd(start, i, shiftIdx, &sc.Config.Shifts)
			se := rotang.ShiftEntry{
				Name:      shift.Name,
				StartTime: shiftStart,
				EndTime:   shiftEnd,
			}
			for oncallIdx := 0; oncallIdx < sc.Config.Shifts.ShiftMembers; j++ {
				propMember := cm[j%len(cm)]
				if PersonalOutage(shiftStart, sc.Config.Shifts.Length, sc.Config.Shifts.Shifts[shiftIdx].Duration, propMember) {
					continue
				}
				se.OnCall = append(se.OnCall, rotang.ShiftMember{
					Email:     propMember.Email,
					ShiftName: shift.Name,
				})
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
