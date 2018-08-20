package algo

import (
	"infra/appengine/rotang"
	"sort"
	"time"
)

type byEmail []rotang.Member

func (b byEmail) Less(i, j int) bool {
	return b[i].Email < b[j].Email
}

func (b byEmail) Len() int {
	return len(b)
}

func (b byEmail) Swap(i, j int) {
	b[i], b[j] = b[j], b[i]
}

// Legacy implements a rota generator similar to the current rotation script.
type Legacy struct {
}

var _ rotang.RotaGenerator = &Legacy{}

// NewLegacy returns a new Legacy rotation Generator.
func NewLegacy() *Legacy {
	return &Legacy{}
}

// Name returns the name of the Legacy Generator.
func (l *Legacy) Name() string {
	return "Legacy"
}

// Generate tries to be similar to the legacy rotation script generator. In short it just produces a list of all members split into PDT members and others.
// It then schedules shifts with PDT members first before dipping into the others pool.
func (l *Legacy) Generate(sc *rotang.Configuration, start time.Time, previous []rotang.ShiftEntry, members []rotang.Member, shiftsToSchedule int) ([]rotang.ShiftEntry, error) {
	var usMembers, otherMembers []rotang.Member
	for _, m := range members {
		if m.TZ.String() != "US/Pacific" {
			otherMembers = append(otherMembers, m)
			continue
		}
		usMembers = append(usMembers, m)
	}

	sort.Sort(byEmail(usMembers))
	sort.Sort(byEmail(otherMembers))
	memberPool := append(usMembers, otherMembers...)

	if len(previous) > 0 {
		start = previous[len(previous)-1].EndTime
	}

	return MakeShifts(sc, start, memberPool, shiftsToSchedule), nil
}
