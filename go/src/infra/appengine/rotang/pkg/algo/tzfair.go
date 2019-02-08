package algo

import (
	"infra/appengine/rotang"
	"sort"
	"time"

	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

// TZFair implements a rota Generator scheduling members according to their timezones.
type TZFair struct {
}

var _ rotang.RotaGenerator = &TZFair{}

// NewTZFair returns and instance of the TZFair generator.
func NewTZFair() *TZFair {
	return &TZFair{}
}

// Generate generates rotations fairly per time-zone.
func (t *TZFair) Generate(sc *rotang.Configuration, start time.Time, previous []rotang.ShiftEntry, members []rotang.Member, shiftsToSchedule int) ([]rotang.ShiftEntry, error) {
	// Turns []rotang.Member into [][]rotang.Member with a slice of members per TZ.
	// The reason for not using a map here is to have the order of TZs consistent.
	sort.Slice(members, func(i, j int) bool {
		return members[i].TZ.String() < members[j].TZ.String()
	})
	var tzMembers [][]rotang.Member
	lastSeen := ""
	for _, m := range members {
		if lastSeen != m.TZ.String() {
			tzMembers = append(tzMembers, []rotang.Member{m})
			lastSeen = m.TZ.String()
			continue
		}
		tzMembers[len(tzMembers)-1] = append(tzMembers[len(tzMembers)-1], m)
	}

	// Since a pointer is used for Generate implying Generate won't change it up; better copy it.
	scCopy := *sc
	scCopy.Config.Shifts.ShiftMembers = 1

	fairGen := NewFair()

	var perTZShifts [][]rotang.ShiftEntry
	for _, ms := range tzMembers {
		shifts, err := fairGen.Generate(&scCopy, start, previous, ms, shiftsToSchedule)
		if err != nil {
			return nil, err
		}
		perTZShifts = append(perTZShifts, shifts)
	}
	return tzSlice(perTZShifts)
}

// Name returns the name of the Generator.
func (t *TZFair) Name() string {
	return "TZFair"
}

// tzSlice turn the slices of rotang.ShiftEntry into a slice of ShiftEntry with
// one member per TZ slice.
//
// tzShifts:
//	"Australia/Sydney"  -> tzShifts[0][]rotang.ShiftEntry{...OnCall: "A@A.com"...}
//	"EST"               -> tzShifts[1][]rotang.ShiftEntry{...OnCall: "B@B.com"...}
//	"US/Pacific"        -> tzShifts[2][]rotang.ShiftEntry{...OnCall: "C@C.com"...}
//	"UTC"               -> tzShifts[3][]rotang.ShiftEntry{...OnCall: "D@D.com"...}
//
// Turns into:
//  []rotang.ShiftEntry{...OnCall: []{"A@A.com", "B@B.com", "C@C.com", "D@D.com"}
func tzSlice(tzShifts [][]rotang.ShiftEntry) ([]rotang.ShiftEntry, error) {
	if len(tzShifts) < 1 || len(tzShifts[0]) < 1 {
		return nil, nil
	}
	if len(tzShifts) == 1 {
		return tzShifts[0], nil
	}
	firstLen := len(tzShifts[0])
	for i := 0; i < len(tzShifts); i++ {
		if len(tzShifts[i]) != firstLen {
			return nil, status.Errorf(codes.InvalidArgument, "shifts not same length")
		}
	}
	for si := range tzShifts[0] {
		for i := 1; i < len(tzShifts); i++ {
			tzShifts[0][si].OnCall = append(tzShifts[0][si].OnCall, tzShifts[i][si].OnCall[0])
		}
	}
	return tzShifts[0], nil
}
