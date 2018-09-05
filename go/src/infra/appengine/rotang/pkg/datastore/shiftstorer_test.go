package datastore

import (
	"infra/appengine/rotang"
	"testing"
	"time"

	"github.com/kylelemons/godebug/pretty"
	"golang.org/x/net/context"
)

var midnight = time.Date(2006, 1, 2, 0, 0, 0, 0, time.UTC)

func TestAddShifts(t *testing.T) {
	ctx := newTestContext()
	ctxCancel, cancel := context.WithCancel(ctx)
	cancel()

	tests := []struct {
		name       string
		fail       bool
		ctx        context.Context
		rota       string
		rotaCfg    *rotang.Configuration
		memberPool []rotang.Member
		existing   []rotang.ShiftEntry
		add        []rotang.ShiftEntry
		want       []rotang.ShiftEntry
	}{{
		name: "Canceled Context",
		fail: true,
		rota: "test rota",
		ctx:  ctxCancel,
		rotaCfg: &rotang.Configuration{
			Config: rotang.Config{
				Description: "Test",
				Name:        "test rota",
			},
		},
	}, {
		name: "Rota does not exist",
		fail: true,
		rota: "don't exist",
		ctx:  ctx,
		rotaCfg: &rotang.Configuration{
			Config: rotang.Config{
				Description: "Test",
				Name:        "test rota",
			},
		},
	}, {
		name: "Shift already exist",
		fail: true,
		rota: "test rota",
		ctx:  ctx,
		rotaCfg: &rotang.Configuration{
			Config: rotang.Config{
				Description: "Test",
				Name:        "test rota",
				Shifts: rotang.ShiftConfig{
					ShiftMembers: 1,
				},
			},
			Members: []rotang.ShiftMember{
				{
					Email: "oncaller@oncall.com",
				},
			},
		},
		memberPool: []rotang.Member{
			{
				Email: "oncaller@oncall.com",
			},
		},
		existing: []rotang.ShiftEntry{
			{
				Name: "MTV All Day",
				OnCall: []rotang.ShiftMember{
					{
						Email: "oncaller@oncall.com",
					},
				},
				StartTime: midnight,
				EndTime:   midnight.Add(8 * time.Hour),
			},
		},
		add: []rotang.ShiftEntry{
			{
				Name: "MTV All Day",
				OnCall: []rotang.ShiftMember{
					{
						Email: "oncaller@oncall.com",
					},
				},
				StartTime: midnight,
				EndTime:   midnight.Add(8 * time.Hour),
			},
		},
	}, {
		name: "Member not in shift",
		fail: true,
		rota: "test rota",
		ctx:  ctx,
		rotaCfg: &rotang.Configuration{
			Config: rotang.Config{
				Description: "Test",
				Name:        "test rota",
				Shifts: rotang.ShiftConfig{
					ShiftMembers: 1,
				},
			},
			Members: []rotang.ShiftMember{
				{
					Email: "oncaller@oncall.com",
				},
			},
		},
		memberPool: []rotang.Member{
			{
				Email: "oncaller@oncall.com",
			},
			{
				Email: "notinshift@oncall.com",
			},
		},
		add: []rotang.ShiftEntry{
			{
				Name: "MTV All Day",
				OnCall: []rotang.ShiftMember{
					{
						Email: "notinshift@oncall.com",
					},
				},
				StartTime: midnight,
				EndTime:   midnight.Add(8 * time.Hour),
			},
		},
	}, {
		name: "Add first shift",
		rota: "test rota",
		ctx:  ctx,
		rotaCfg: &rotang.Configuration{
			Config: rotang.Config{
				Description: "Test",
				Name:        "test rota",
				Shifts: rotang.ShiftConfig{
					ShiftMembers: 1,
				},
			},
			Members: []rotang.ShiftMember{
				{
					Email: "oncaller@oncall.com",
				},
			},
		},
		memberPool: []rotang.Member{
			{
				Email: "oncaller@oncall.com",
			},
		},
		add: []rotang.ShiftEntry{
			{
				Name: "MTV All Day",
				OnCall: []rotang.ShiftMember{
					{
						Email: "oncaller@oncall.com",
					},
				},
				StartTime: midnight,
				EndTime:   midnight.Add(8 * time.Hour),
			},
		},
		want: []rotang.ShiftEntry{
			{
				Name: "MTV All Day",
				OnCall: []rotang.ShiftMember{
					{
						Email: "oncaller@oncall.com",
					},
				},
				StartTime: midnight,
				EndTime:   midnight.Add(8 * time.Hour),
			},
		},
	}, {
		name: "Existing shifts",
		rota: "test rota",
		ctx:  ctx,
		rotaCfg: &rotang.Configuration{
			Config: rotang.Config{
				Description: "Test",
				Name:        "test rota",
				Shifts: rotang.ShiftConfig{
					ShiftMembers: 1,
				},
			},
			Members: []rotang.ShiftMember{
				{
					Email: "oncaller1@oncall.com",
				},
				{
					Email: "oncaller2@oncall.com",
				},
				{
					Email: "oncaller3@oncall.com",
				},
				{
					Email: "oncaller4@oncall.com",
				},
			},
		},
		memberPool: []rotang.Member{
			{
				Email: "oncaller1@oncall.com",
			},
			{
				Email: "oncaller2@oncall.com",
			},
			{
				Email: "oncaller3@oncall.com",
			},
			{
				Email: "oncaller4@oncall.com",
			},
		},
		existing: []rotang.ShiftEntry{
			{
				Name: "MTV All Day",
				OnCall: []rotang.ShiftMember{
					{
						Email: "oncaller1@oncall.com",
					},
				},
				StartTime: midnight,
				EndTime:   midnight.Add(8 * time.Hour),
			}, {
				Name: "MTV All Day",
				OnCall: []rotang.ShiftMember{
					{
						Email: "oncaller4@oncall.com",
					},
				},
				StartTime: midnight.Add(3 * 8 * time.Hour),
				EndTime:   midnight.Add(4 * 8 * time.Hour),
			},
		},
		add: []rotang.ShiftEntry{
			{
				Name: "MTV All Day",
				OnCall: []rotang.ShiftMember{
					{
						Email: "oncaller2@oncall.com",
					},
				},
				StartTime: midnight.Add(8 * time.Hour),
				EndTime:   midnight.Add(2 * 8 * time.Hour),
			},
			{
				Name: "MTV All Day",
				OnCall: []rotang.ShiftMember{
					{
						Email: "oncaller3@oncall.com",
					},
				},
				StartTime: midnight.Add(2 * 8 * time.Hour),
				EndTime:   midnight.Add(3 * 8 * time.Hour),
			},
		},
		want: []rotang.ShiftEntry{
			{
				Name: "MTV All Day",
				OnCall: []rotang.ShiftMember{
					{
						Email: "oncaller1@oncall.com",
					},
				},
				StartTime: midnight,
				EndTime:   midnight.Add(8 * time.Hour),
			}, {
				Name: "MTV All Day",
				OnCall: []rotang.ShiftMember{
					{
						Email: "oncaller2@oncall.com",
					},
				},
				StartTime: midnight.Add(8 * time.Hour),
				EndTime:   midnight.Add(2 * 8 * time.Hour),
			}, {
				Name: "MTV All Day",
				OnCall: []rotang.ShiftMember{
					{
						Email: "oncaller3@oncall.com",
					},
				},
				StartTime: midnight.Add(2 * 8 * time.Hour),
				EndTime:   midnight.Add(3 * 8 * time.Hour),
			}, {
				Name: "MTV All Day",
				OnCall: []rotang.ShiftMember{
					{
						Email: "oncaller4@oncall.com",
					},
				},
				StartTime: midnight.Add(3 * 8 * time.Hour),
				EndTime:   midnight.Add(4 * 8 * time.Hour),
			},
		},
	},
	}

	store := New(ctx)

	for _, tst := range tests {
		t.Run(tst.name, func(t *testing.T) {
			for _, m := range tst.memberPool {
				if err := store.CreateMember(ctx, &m); err != nil {
					t.Fatalf("%s: store.CreateMember(ctx, _) failed: %v", tst.name, err)
				}
				defer store.DeleteMember(ctx, m.Email)
			}
			if err := store.CreateRotaConfig(ctx, tst.rotaCfg); err != nil {
				t.Fatalf("%s: store.CreateRotaConfig(ctx, _) failed: %v", tst.name, err)
			}
			defer store.DeleteRotaConfig(ctx, tst.rotaCfg.Config.Name)
			for _, s := range tst.existing {
				if err := store.AddShifts(ctx, tst.rotaCfg.Config.Name, []rotang.ShiftEntry{s}); err != nil {
					t.Fatalf("%s: store.AddShifts(ctx, %q) failed: %v", tst.name, tst.rotaCfg.Config.Name, err)
				}
			}

			defer store.DeleteAllShifts(ctx, tst.rota)

			err := store.AddShifts(tst.ctx, tst.rota, tst.add)
			if got, want := (err != nil), tst.fail; got != want {
				t.Fatalf("%s: store.AddShifts(ctx, %q, _) = %t want: %t, err: %v", tst.name, tst.rota, got, want, err)
			}
			if err != nil {
				return
			}
			shifts, err := store.AllShifts(ctx, tst.rota)
			if err != nil {
				t.Fatalf("%s: store.AllShifts(ctx, %q) failed: %v", tst.name, tst.rota, err)
			}
			if diff := pretty.Compare(tst.want, shifts); diff != "" {
				t.Fatalf("%s: store.AllShifts(ctx, %q) differ -want +got, %s", tst.name, tst.rota, diff)
			}
		})
	}
}
