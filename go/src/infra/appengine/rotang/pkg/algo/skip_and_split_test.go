package algo

import (
	"testing"
	"time"

	"infra/appengine/rotang"

	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

func checkWeekend(t *testing.T, ss []rotang.ShiftEntry) error {
	t.Helper()
	for _, s := range ss {
		switch {
		case s.StartTime.Weekday() == time.Saturday:
			return status.Errorf(codes.Internal, "shift, Start: %v, End: %v, StartTime on a Saturday", s.StartTime, s.EndTime)
		case s.StartTime.Weekday() == time.Sunday:
			return status.Errorf(codes.Internal, "shift, Start: %v, End: %v, StartTime on a Sunday", s.StartTime, s.EndTime)
		case s.EndTime.Weekday() == time.Sunday:
			return status.Errorf(codes.Internal, "shift, Start: %v, End: %v, EndTime on a Saturday", s.StartTime, s.EndTime)
		case s.EndTime.Weekday() == time.Monday:
			return status.Errorf(codes.Internal, "shift, Start: %v, End: %v, EndTime on a Monday", s.StartTime, s.EndTime)
		}
	}
	return nil
}

func checkSplit(t *testing.T, ss []rotang.ShiftEntry) error {
	t.Helper()
	for _, s := range ss {
		if s.EndTime.Sub(s.StartTime) != fullDay {
			return status.Errorf(codes.Internal, "shift: %v Start: %v, End: %v, Duration: %v not full day", s, s.StartTime, s.EndTime, s.EndTime.Sub(s.StartTime))
		}
	}
	return nil
}

func TestMultiModify(t *testing.T) {

	tests := []struct {
		name             string
		fail             bool
		cfg              *rotang.Configuration
		members          string
		shifts           string
		generator        string
		modifiers        []string
		lenRange         [2]int
		shiftsToSchedule int
		checkFunc        func(*testing.T, []rotang.ShiftEntry) error
	}{{
		name: "WeekendSkip - Only",
		cfg: &rotang.Configuration{
			Config: rotang.Config{
				Shifts: rotang.ShiftConfig{
					Length:       3,
					ShiftMembers: 1,
					TZ:           *time.UTC,
					Shifts: []rotang.Shift{
						{
							Name:     "MTV All Day",
							Duration: fullDay,
						},
					},
				},
			},
		},
		lenRange:         [2]int{1, 14},
		members:          "ABCDEFGHIJK",
		shifts:           "ABCDEFGHIJK",
		generator:        "Recent",
		modifiers:        []string{"WeekendSkip"},
		shiftsToSchedule: 10,
		checkFunc:        checkWeekend,
	}, {
		name: "WeekendSkip and Split",
		cfg: &rotang.Configuration{
			Config: rotang.Config{
				Shifts: rotang.ShiftConfig{
					Length:       4,
					ShiftMembers: 1,
					TZ:           *time.UTC,
					Shifts: []rotang.Shift{
						{
							Name:     "MTV All Day",
							Duration: fullDay,
						},
					},
				},
			},
		},
		lenRange:         [2]int{1, 14},
		members:          "ABCDEFGHIJK",
		shifts:           "ABCDEFGHIJK",
		generator:        "Recent",
		modifiers:        []string{"WeekendSkip", "SplitShift"},
		shiftsToSchedule: 10,
		checkFunc:        checkWeekend,
	}, {
		name: "SplitShift and WeekendSplit",
		cfg: &rotang.Configuration{
			Config: rotang.Config{
				Shifts: rotang.ShiftConfig{
					Length:       5,
					ShiftMembers: 1,
					TZ:           *time.UTC,
					Shifts: []rotang.Shift{
						{
							Name:     "MTV All Day",
							Duration: fullDay,
						},
					},
				},
			},
		},
		lenRange:         [2]int{1, 14},
		members:          "ABCDEFGHIJK",
		shifts:           "ABCDEFGHIJK",
		generator:        "Recent",
		modifiers:        []string{"WeekendSkip", "SplitShift"},
		shiftsToSchedule: 10,
		checkFunc:        checkWeekend,
	}, {
		name: "SplitShift - Only",
		cfg: &rotang.Configuration{
			Config: rotang.Config{
				Shifts: rotang.ShiftConfig{
					Length:       5,
					ShiftMembers: 1,
					TZ:           *time.UTC,
					Shifts: []rotang.Shift{
						{
							Name:     "MTV All Day",
							Duration: fullDay,
						},
					},
				},
			},
		},
		lenRange:         [2]int{1, 14},
		members:          "ABCDEFGHIJK",
		shifts:           "ABCDEFGHIJK",
		generator:        "Recent",
		modifiers:        []string{"WeekendSkip", "SplitShift"},
		shiftsToSchedule: 10,
		checkFunc:        checkSplit,
	}}

	// Sort out the generators.
	gs := New()
	gs.Register(NewLegacy())
	gs.Register(NewFair())
	gs.Register(NewRandomGen())
	gs.Register(NewTZFair())
	gs.Register(NewRecent())
	gs.Register(NewTZRecent())

	// And the modifiers.
	gs.RegisterModifier(NewWeekendSkip())
	gs.RegisterModifier(NewSplitShift())

L1:
	for _, tst := range tests {
		var modifiers []rotang.ShiftModifier
		for _, m := range tst.modifiers {
			m, err := gs.FetchModifier(m)
			if err != nil {
				t.Errorf("%s: FetchModifier(%q) failed: %v", tst.name, m, err)
				continue L1
			}
			modifiers = append(modifiers, m)
		}
		g, err := gs.Fetch(tst.generator)
		if err != nil {
			t.Errorf("%s: Fetch(%q) failed: %v", tst.name, tst.generator, err)
			continue
		}
		shifts := stringToShifts(tst.shifts, "MTV All Day")
		members := stringToMembers(tst.members, mtvTime)

		tst.cfg.Members = stringToShiftMembers(tst.members, "MTV All Day")

		for i := tst.lenRange[0]; i < tst.lenRange[1]; i++ {
			tst.cfg.Config.Shifts.Length = i
			se, err := g.Generate(tst.cfg, time.Now(), shifts, members, tst.shiftsToSchedule)
			if err != nil {
				t.Errorf("%s: shiftLen: %d, Generate failed: %v", tst.name, i, err)
				continue
			}
			for _, m := range modifiers {
				if se, err = m.Modify(&tst.cfg.Config.Shifts, se); err != nil {
					t.Errorf("%s: shiftLen: %d, Modify failed: %v", tst.name, i, err)
					continue L1
				}
			}
			if err := tst.checkFunc(t, se); err != nil {
				t.Errorf("%s: shiftLen: %d checkFunc() failed: %v", tst.name, i, err)
			}
		}
	}
}
