package algo

import (
	"infra/appengine/rotang"
	"time"
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
			// When splitting or moving a shift, all following shifts
			// need to be adjusted too. Skip identifies how much to add
			// to each shift.
			skip := fullDay
			switch st.Weekday() {
			case time.Saturday:
				// If the shift starts at a Saturday -> move it no split needed.
				if st.Equal(start) {
					break
				}
				// Split the shift into two.
				shifts[i].EndTime = st
				newShift := shifts[i]
				newShift.StartTime = shifts[i].StartTime.Add(skip)
				newShift.EndTime = shifts[i].EndTime.Add(skip)

				skip = 2 * fullDay
				i++
				shifts = append(shifts[:i], append([]rotang.ShiftEntry{newShift}, shifts[i:]...)...)
			case time.Sunday:
				// Just move the shift StartTime and EndTime forward one day.
			default:
				continue
			}
			for j := i; j < len(shifts); j++ {
				shifts[j].StartTime, shifts[j].EndTime = shifts[j].StartTime.Add(skip), shifts[j].EndTime.Add(skip)
			}
		}
	}
	return shifts, nil
}
