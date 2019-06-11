package algo

import (
	"infra/appengine/rotang"
	"time"

	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

// WeekendSkip implements the ShiftModifier interface.
type WeekendSkip struct {
}

var _ rotang.ShiftModifier = &WeekendSkip{}

// NewWeekendSkip returns a new instance of the WeekendSkip modifier.
func NewWeekendSkip() *WeekendSkip {
	return &WeekendSkip{}
}

// Name returns the name of this ShiftModifier.
func (w *WeekendSkip) Name() string {
	return "WeekendSkip"
}

// Description describes the ShiftModifier.
func (w *WeekendSkip) Description() string {
	return "Does not schedule shifts on weekends ,  Sat & Sun."
}

// Modify modifies provided shifts to avoid weekends.
// Eg.
//   Shift Fri - Sat
// Will be split up in to two shifts.
//  Shift1 - Fri
//  Shift2 - Monday
//
//  A shift generated for 'Sat - Sun'
//	Will be moved forward to Mon - Tue
//
// All shifts following a modified shift will be moved accordingly.
// Eg.
//     Shift  Days
//      1     Mon - Tue
//      2     Wed - Thu
//      3     Fri - Sat
//      4     Sun - Mon
//      5     Tue - Wed
//			6			Thu - Fri
//
// Turns in to:
//
//		Shift		Days
//		  1			Mon - Tue
//			2			Wed - Thu
//			3			Friday
//			4			Monday
//			5			Tue - Wed
//			6     Thu - Fri
//			7			Mon - Tue
func (w *WeekendSkip) Modify(sc *rotang.ShiftConfig, shifts []rotang.ShiftEntry) ([]rotang.ShiftEntry, error) {
	for i := 0; i < len(shifts); i++ {
		start, end := shifts[i].StartTime.In(&sc.TZ), shifts[i].EndTime.In(&sc.TZ)
		for st := start; st.Before(end); st = st.Add(fullDay) {
			if st.Weekday() == time.Saturday || st.Weekday() == time.Sunday {
				// Shift having a day on a weekend needs to be split.
				if !st.Equal(start) {
					var err error
					shifts, err = splitShift(shifts, st, i)
					if err != nil {
						return nil, err
					}
					break
				}
				// If the shift starts on a Saturday or Sunday move it and all past shifts forward.
				moveShifts(shifts[i:], fullDay)
				start, end = start.Add(fullDay), end.Add(fullDay)
			}
		}
	}
	return shifts, nil
}

// splitShift splits the indicated shift in two.
func splitShift(shifts []rotang.ShiftEntry, splitTime time.Time, idx int) ([]rotang.ShiftEntry, error) {
	if len(shifts) <= idx {
		return nil, status.Errorf(codes.OutOfRange, "index out of range")
	}
	newShift := shifts[idx]
	shifts[idx].EndTime, newShift.StartTime = splitTime, splitTime
	idx++
	return append(shifts[:idx], append([]rotang.ShiftEntry{newShift}, shifts[idx:]...)...), nil
}

// moveShifts move the start and end times of the shifts forward.
func moveShifts(shifts []rotang.ShiftEntry, timeAdd time.Duration) {
	for i := range shifts {
		shifts[i].StartTime, shifts[i].EndTime = shifts[i].StartTime.Add(timeAdd), shifts[i].EndTime.Add(timeAdd)
	}
}
