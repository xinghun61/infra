package algo

import (
	"infra/appengine/rotang"
	"testing"
	"time"

	"github.com/kylelemons/godebug/pretty"
)

const (
	pacificTZ = "US/Pacific"
	estTZ     = "EST"
	apacTZ    = "Australia/Sydney"
	euTZ      = "UTC"
)

type memberTZ struct {
	members string
	TZ      *time.Location
}

func TestGenerateTZFair(t *testing.T) {

	pacificLocation, err := time.LoadLocation(pacificTZ)
	if err != nil {
		t.Fatalf("time.LoadLocation(%q) failed: %v", pacificTZ, err)
	}
	euLocation, err := time.LoadLocation(euTZ)
	if err != nil {
		t.Fatalf("time.LoadLocation(%q) failed: %v", euTZ, err)
	}
	estLocation, err := time.LoadLocation(estTZ)
	if err != nil {
		t.Fatalf("time.LoadLocation(%q) failed: %v", estTZ, err)
	}
	apacLocation, err := time.LoadLocation(apacTZ)
	if err != nil {
		t.Fatalf("time.LoadLocation(%q) failed: %v", apacTZ, err)
	}

	tests := []struct {
		name      string
		fail      bool
		cfg       *rotang.Configuration
		start     time.Time
		members   []memberTZ
		numShifts int
		previous  string
		want      []rotang.ShiftEntry
	}{
		{
			name: "Single TZ",
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
			members: []memberTZ{{
				members: "ABCDEF",
				TZ:      mtvTime,
			}},
			previous: "ABCDEF",
			want: []rotang.ShiftEntry{
				{
					Name: "Test Shift",
					OnCall: []rotang.ShiftMember{
						{
							Email:     "F@F.com",
							ShiftName: "Test Shift",
						},
					},
					StartTime: midnight.Add(2*fullDay + 2*fullDay),                         // Shift skips two days.
					EndTime:   midnight.Add(fullDay + 5*fullDay + time.Hour*8 + 2*fullDay), // Length of the shift is 5 days.
					Comment:   "",
				}, {
					Name: "Test Shift",
					OnCall: []rotang.ShiftMember{
						{
							Email:     "E@E.com",
							ShiftName: "Test Shift",
						},
					},
					StartTime: midnight.Add(9*fullDay + 2*fullDay),
					EndTime:   midnight.Add(8*fullDay + 5*fullDay + time.Hour*8 + 2*fullDay),
					Comment:   "",
				}, {
					Name: "Test Shift",
					OnCall: []rotang.ShiftMember{
						{
							Email:     "D@D.com",
							ShiftName: "Test Shift",
						},
					},
					StartTime: midnight.Add(16*fullDay + 2*fullDay),
					EndTime:   midnight.Add(15*fullDay + 5*fullDay + time.Hour*8 + 2*fullDay),
					Comment:   "",
				}, {
					Name: "Test Shift",
					OnCall: []rotang.ShiftMember{
						{
							Email:     "C@C.com",
							ShiftName: "Test Shift",
						},
					},
					StartTime: midnight.Add(23*fullDay + 2*fullDay),
					EndTime:   midnight.Add(22*fullDay + 5*fullDay + time.Hour*8 + 2*fullDay),
					Comment:   "",
				}, {
					Name: "Test Shift",
					OnCall: []rotang.ShiftMember{
						{
							Email:     "B@B.com",
							ShiftName: "Test Shift",
						},
					},
					StartTime: midnight.Add(30*fullDay + 2*fullDay),
					EndTime:   midnight.Add(29*fullDay + 5*fullDay + time.Hour*8 + 2*fullDay),
					Comment:   "",
				}, {
					Name: "Test Shift",
					OnCall: []rotang.ShiftMember{
						{
							Email:     "A@A.com",
							ShiftName: "Test Shift",
						},
					},
					StartTime: midnight.Add(37*fullDay + 2*fullDay),
					EndTime:   midnight.Add(36*fullDay + 5*fullDay + time.Hour*8 + 2*fullDay),
					Comment:   "",
				}, {
					Name: "Test Shift",
					OnCall: []rotang.ShiftMember{
						{
							Email:     "F@F.com",
							ShiftName: "Test Shift",
						},
					},
					StartTime: midnight.Add(44*fullDay + 2*fullDay),
					EndTime:   midnight.Add(43*fullDay + 5*fullDay + time.Hour*8 + 2*fullDay),
					Comment:   "",
				}, {
					Name: "Test Shift",
					OnCall: []rotang.ShiftMember{
						{
							Email:     "E@E.com",
							ShiftName: "Test Shift",
						},
					},
					StartTime: midnight.Add(51*fullDay + 2*fullDay),
					EndTime:   midnight.Add(50*fullDay + 5*fullDay + time.Hour*8 + 2*fullDay),
					Comment:   "",
				}, {
					Name: "Test Shift",
					OnCall: []rotang.ShiftMember{
						{
							Email:     "D@D.com",
							ShiftName: "Test Shift",
						},
					},
					StartTime: midnight.Add(58*fullDay + 2*fullDay),
					EndTime:   midnight.Add(57*fullDay + 5*fullDay + time.Hour*8 + 2*fullDay),
					Comment:   "",
				}, {
					Name: "Test Shift",
					OnCall: []rotang.ShiftMember{
						{
							Email:     "C@C.com",
							ShiftName: "Test Shift",
						},
					},
					StartTime: midnight.Add(65*fullDay + 2*fullDay),
					EndTime:   midnight.Add(64*fullDay + 5*fullDay + time.Hour*8 + 2*fullDay),
					Comment:   "",
				},
			},
		}, {
			name: "Multi TZ",
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
						ShiftMembers: 4,
						Generator:    "Fair",
					},
				},
			},
			numShifts: 9,
			members: []memberTZ{{
				members: "ABC",
				TZ:      apacLocation,
			}, {
				members: "DEF",
				TZ:      estLocation,
			}, {
				members: "GHI",
				TZ:      pacificLocation,
			}, {
				members: "JKL",
				TZ:      euLocation,
			},
			},
			previous: "ABCDEFGHIJKL",
			want: []rotang.ShiftEntry{
				{
					Name: "Test Shift",
					OnCall: []rotang.ShiftMember{
						{
							Email:     "C@C.com",
							ShiftName: "Test Shift",
						}, {
							Email:     "F@F.com",
							ShiftName: "Test Shift",
						}, {
							Email:     "I@I.com",
							ShiftName: "Test Shift",
						}, {
							Email:     "L@L.com",
							ShiftName: "Test Shift",
						},
					},
					StartTime: midnight.Add(2*fullDay + 2*fullDay),                         // Shift skips two days.
					EndTime:   midnight.Add(fullDay + 5*fullDay + time.Hour*8 + 2*fullDay), // Length of the shift is 5 days.
				}, {
					Name: "Test Shift",
					OnCall: []rotang.ShiftMember{
						{
							Email:     "B@B.com",
							ShiftName: "Test Shift",
						}, {
							Email:     "E@E.com",
							ShiftName: "Test Shift",
						}, {
							Email:     "H@H.com",
							ShiftName: "Test Shift",
						}, {
							Email:     "K@K.com",
							ShiftName: "Test Shift",
						},
					},
					StartTime: midnight.Add(9*fullDay + 2*fullDay),
					EndTime:   midnight.Add(8*fullDay + 5*fullDay + time.Hour*8 + 2*fullDay),
				}, {
					Name: "Test Shift",
					OnCall: []rotang.ShiftMember{
						{
							Email:     "A@A.com",
							ShiftName: "Test Shift",
						}, {
							Email:     "D@D.com",
							ShiftName: "Test Shift",
						}, {
							Email:     "G@G.com",
							ShiftName: "Test Shift",
						}, {
							Email:     "J@J.com",
							ShiftName: "Test Shift",
						},
					},
					StartTime: midnight.Add(16*fullDay + 2*fullDay),
					EndTime:   midnight.Add(15*fullDay + 5*fullDay + time.Hour*8 + 2*fullDay),
				}, {
					Name: "Test Shift",
					OnCall: []rotang.ShiftMember{
						{
							Email:     "C@C.com",
							ShiftName: "Test Shift",
						}, {
							Email:     "F@F.com",
							ShiftName: "Test Shift",
						}, {
							Email:     "I@I.com",
							ShiftName: "Test Shift",
						}, {
							Email:     "L@L.com",
							ShiftName: "Test Shift",
						},
					},
					StartTime: midnight.Add(23*fullDay + 2*fullDay),
					EndTime:   midnight.Add(22*fullDay + 5*fullDay + time.Hour*8 + 2*fullDay),
				}, {
					Name: "Test Shift",
					OnCall: []rotang.ShiftMember{
						{
							Email:     "B@B.com",
							ShiftName: "Test Shift",
						}, {
							Email:     "E@E.com",
							ShiftName: "Test Shift",
						}, {
							Email:     "H@H.com",
							ShiftName: "Test Shift",
						}, {
							Email:     "K@K.com",
							ShiftName: "Test Shift",
						},
					},
					StartTime: midnight.Add(30*fullDay + 2*fullDay),
					EndTime:   midnight.Add(29*fullDay + 5*fullDay + time.Hour*8 + 2*fullDay),
				}, {
					Name: "Test Shift",
					OnCall: []rotang.ShiftMember{
						{
							Email:     "A@A.com",
							ShiftName: "Test Shift",
						}, {
							Email:     "D@D.com",
							ShiftName: "Test Shift",
						}, {
							Email:     "G@G.com",
							ShiftName: "Test Shift",
						}, {
							Email:     "J@J.com",
							ShiftName: "Test Shift",
						},
					},
					StartTime: midnight.Add(37*fullDay + 2*fullDay),
					EndTime:   midnight.Add(36*fullDay + 5*fullDay + time.Hour*8 + 2*fullDay),
				}, {
					Name: "Test Shift",
					OnCall: []rotang.ShiftMember{
						{
							Email:     "C@C.com",
							ShiftName: "Test Shift",
						}, {
							Email:     "F@F.com",
							ShiftName: "Test Shift",
						}, {
							Email:     "I@I.com",
							ShiftName: "Test Shift",
						}, {
							Email:     "L@L.com",
							ShiftName: "Test Shift",
						},
					},
					StartTime: midnight.Add(44*fullDay + 2*fullDay),
					EndTime:   midnight.Add(43*fullDay + 5*fullDay + time.Hour*8 + 2*fullDay),
				}, {
					Name: "Test Shift",
					OnCall: []rotang.ShiftMember{
						{
							Email:     "B@B.com",
							ShiftName: "Test Shift",
						}, {
							Email:     "E@E.com",
							ShiftName: "Test Shift",
						}, {
							Email:     "H@H.com",
							ShiftName: "Test Shift",
						}, {
							Email:     "K@K.com",
							ShiftName: "Test Shift",
						},
					},
					StartTime: midnight.Add(51*fullDay + 2*fullDay),
					EndTime:   midnight.Add(50*fullDay + 5*fullDay + time.Hour*8 + 2*fullDay),
				}, {
					Name: "Test Shift",
					OnCall: []rotang.ShiftMember{
						{
							Email:     "A@A.com",
							ShiftName: "Test Shift",
						}, {
							Email:     "D@D.com",
							ShiftName: "Test Shift",
						}, {
							Email:     "G@G.com",
							ShiftName: "Test Shift",
						}, {
							Email:     "J@J.com",
							ShiftName: "Test Shift",
						},
					},
					StartTime: midnight.Add(58*fullDay + 2*fullDay),
					EndTime:   midnight.Add(57*fullDay + 5*fullDay + time.Hour*8 + 2*fullDay),
				},
			},
		},
	}

	as := New()
	as.Register(NewTZFair())
	generator, err := as.Fetch("TZFair")
	if err != nil {
		t.Fatalf("as.Fetch(%q) failed: %v", "TZFair", err)
	}

	for _, tst := range tests {
		var members []rotang.Member
		for _, m := range tst.members {
			tst.cfg.Members = append(tst.cfg.Members, stringToShiftMembers(m.members, "Test Shift")...)
			members = append(members, stringToMembers(m.members, m.TZ)...)
		}
		shifts, err := generator.Generate(tst.cfg, tst.start, stringToShifts(tst.previous, tst.cfg.Config.Shifts.Shifts[0].Name), members, tst.numShifts)
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
