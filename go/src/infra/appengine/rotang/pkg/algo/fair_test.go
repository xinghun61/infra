package algo

import (
	"fmt"
	"infra/appengine/rotang"
	"math/rand"
	"testing"
	"time"

	"github.com/kylelemons/godebug/pretty"
)

var midnight = time.Date(2006, 1, 2, 0, 0, 0, 0, time.UTC)

func stringToShifts(in string) []rotang.ShiftEntry {
	var res []rotang.ShiftEntry
	for tm, c := range in {
		baseTime := midnight.Add(time.Duration(len(in)-tm) * time.Hour * 24)
		res = append(res, rotang.ShiftEntry{
			StartTime: baseTime,
			EndTime:   baseTime.Add(time.Hour * 24),
			OnCall: []rotang.ShiftMember{
				{
					Email:     fmt.Sprintf("%c@%c.com", c, c),
					ShiftName: "MTV all day",
				},
			},
			Comment: "stringToShifts",
		})

	}
	return res
}

func stringToMembers(in string) []rotang.Member {
	var res []rotang.Member
	for _, c := range in {
		res = append(res, rotang.Member{
			Email: fmt.Sprintf("%c@%c.com", c, c),
		})
	}
	return res
}

func membersToString(members []rotang.Member) string {
	var res []byte
	for _, m := range members {
		res = append(res, m.Email[0])
	}
	return string(res)
}

func TestMakeFair(t *testing.T) {

	tests := []struct {
		name    string
		shifts  string
		members string
		want    string
	}{{
		name:    "Simple reverse",
		shifts:  "ABCDEFGHI",
		members: "ABCDEFGHI",
		want:    "IHGFEDCBA",
	}, {
		name:    "Member not in previous",
		shifts:  "ABCDEGHI",
		members: "ABCDEFGHI",
		want:    "FIHGEDCBA",
	}, {
		name:    "Member scheduled multiple times",
		shifts:  "BCDEFGHIAB",
		members: "ABCDEFGHI",
		want:    "AIHGFEDCB",
	}, {
		name:    "Recent vs multiple times",
		shifts:  "ABCDEFGHII",
		members: "ABCDEFGHI",
		want:    "HGFEDICBA",
	}, {
		name:    "Recent and multiple",
		shifts:  "ABCDEFGHIIA",
		members: "ABCDEFGHI",
		want:    "HGFEDCIBA",
	}, {
		name:    "Recent multiple and not in there",
		shifts:  "ABCDEGCHIJA",
		members: "ABCDEFGHIJ",
		want:    "FJIHGEDBAC",
	}}

	for _, tst := range tests {
		res := makeFair(stringToMembers(tst.members), stringToShifts(tst.shifts))
		if got, want := membersToString(res), tst.want; got != want {
			t.Errorf("%s: makeFair(_, _ ) = %q want: %q", tst.name, got, want)
		}
	}
}

func TestGenerateFair(t *testing.T) {
	tests := []struct {
		name      string
		fail      bool
		cfg       *rotang.Configuration
		start     time.Time
		members   string
		numShifts int
		previous  string
		want      []rotang.ShiftEntry
	}{
		{
			name: "Simple reverse",
			cfg: &rotang.Configuration{
				Config: rotang.Config{
					Name: "Test Rota",
					Shifts: rotang.ShiftConfig{
						Length: 5,
						Skip:   2,
						Shifts: []rotang.Shift{
							{
								Name:     "Test Shift",
								Duration: time.Hour * 8,
							},
						},
						ShiftMembers: 1,
						Generator:    "Fair",
					},
				},
			},
			numShifts: 10,
			members:   "ABCDEF",
			previous:  "ABCDEF",
			want: []rotang.ShiftEntry{
				{
					Name: "Test Shift",
					OnCall: []rotang.ShiftMember{
						{
							Email:     "F@F.com",
							ShiftName: "Test Shift",
						},
					},
					StartTime: midnight.Add(2 * fullDay),           // Shift skips two days.
					EndTime:   midnight.Add(2*fullDay + 5*fullDay), // Length of the shift is 5 days.
					Comment:   "",
				}, {
					Name: "Test Shift",
					OnCall: []rotang.ShiftMember{
						{
							Email:     "E@E.com",
							ShiftName: "Test Shift",
						},
					},
					StartTime: midnight.Add(9 * fullDay),
					EndTime:   midnight.Add(9*fullDay + 5*fullDay),
					Comment:   "",
				}, {
					Name: "Test Shift",
					OnCall: []rotang.ShiftMember{
						{
							Email:     "D@D.com",
							ShiftName: "Test Shift",
						},
					},
					StartTime: midnight.Add(16 * fullDay),
					EndTime:   midnight.Add(16*fullDay + 5*fullDay),
					Comment:   "",
				}, {
					Name: "Test Shift",
					OnCall: []rotang.ShiftMember{
						{
							Email:     "C@C.com",
							ShiftName: "Test Shift",
						},
					},
					StartTime: midnight.Add(23 * fullDay),
					EndTime:   midnight.Add(23*fullDay + 5*fullDay),
					Comment:   "",
				}, {
					Name: "Test Shift",
					OnCall: []rotang.ShiftMember{
						{
							Email:     "B@B.com",
							ShiftName: "Test Shift",
						},
					},
					StartTime: midnight.Add(30 * fullDay),
					EndTime:   midnight.Add(30*fullDay + 5*fullDay),
					Comment:   "",
				}, {
					Name: "Test Shift",
					OnCall: []rotang.ShiftMember{
						{
							Email:     "A@A.com",
							ShiftName: "Test Shift",
						},
					},
					StartTime: midnight.Add(37 * fullDay),
					EndTime:   midnight.Add(37*fullDay + 5*fullDay),
					Comment:   "",
				}, {
					Name: "Test Shift",
					OnCall: []rotang.ShiftMember{
						{
							Email:     "F@F.com",
							ShiftName: "Test Shift",
						},
					},
					StartTime: midnight.Add(44 * fullDay),
					EndTime:   midnight.Add(44*fullDay + 5*fullDay),
					Comment:   "",
				}, {
					Name: "Test Shift",
					OnCall: []rotang.ShiftMember{
						{
							Email:     "E@E.com",
							ShiftName: "Test Shift",
						},
					},
					StartTime: midnight.Add(51 * fullDay),
					EndTime:   midnight.Add(51*fullDay + 5*fullDay),
					Comment:   "",
				}, {
					Name: "Test Shift",
					OnCall: []rotang.ShiftMember{
						{
							Email:     "D@D.com",
							ShiftName: "Test Shift",
						},
					},
					StartTime: midnight.Add(58 * fullDay),
					EndTime:   midnight.Add(58*fullDay + 5*fullDay),
					Comment:   "",
				}, {
					Name: "Test Shift",
					OnCall: []rotang.ShiftMember{
						{
							Email:     "C@C.com",
							ShiftName: "Test Shift",
						},
					},
					StartTime: midnight.Add(65 * fullDay),
					EndTime:   midnight.Add(65*fullDay + 5*fullDay),
					Comment:   "",
				},
			},
		},
	}

	// Should give the same pseudo random sequence every time.
	rand.Seed(7357)

	as := New()
	as.Register(NewFair())
	generator, err := as.Fetch("Fair")
	if err != nil {
		t.Fatalf("as.Fetch(%q) failed: %v", "Fair", err)
	}

	for _, tst := range tests {
		shifts, err := generator.Generate(tst.cfg, tst.start, stringToShifts(tst.previous), stringToMembers(tst.members), tst.numShifts)
		if got, want := (err != nil), tst.fail; got != want {
			t.Errorf("%s: Generate(_) = %t want: %t, err: %v", tst.name, got, want, err)
			continue
		}
		if err != nil {
			continue
		}
		if diff := pretty.Compare(tst.want, shifts); diff != "" {
			t.Errorf("%s: Generate(_) differs -want +got: %s", tst.name, diff)
		}
	}
}
