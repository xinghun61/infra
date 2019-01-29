package algo

import "infra/appengine/rotang"

// SplitShift splits shifts into single day shifts.
type SplitShift struct {
}

var _ rotang.ShiftModifier = &SplitShift{}

// NewSplitShift returns a new instance of the SplitShift modifier.
func NewSplitShift() *SplitShift {
	return &SplitShift{}
}

// Name returns the name of the SplitShift modifier.
func (s *SplitShift) Name() string {
	return "SplitShift"
}

// Description returns a short description of the shift modifier.
func (s *SplitShift) Description() string {
	return "Splits shifts up into single day shifts."
}

// Modify splits the shifts into one day shifts.
func (s *SplitShift) Modify(sc *rotang.ShiftConfig, shifts []rotang.ShiftEntry) ([]rotang.ShiftEntry, error) {
	for i := 0; i < len(shifts); i++ {
		start, end := shifts[i].StartTime.In(&sc.TZ), shifts[i].EndTime.In(&sc.TZ)
		for st := start.Add(fullDay); st.Before(end); st = st.Add(fullDay) {
			newShift := shifts[i]
			shifts[i].EndTime = st
			newShift.StartTime = st
			i++
			shifts = append(shifts[:i], append([]rotang.ShiftEntry{newShift}, shifts[i:]...)...)
		}
	}
	return shifts, nil
}
