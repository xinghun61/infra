package datastore

import (
	"infra/appengine/rotang"
	"infra/appengine/rotang/pkg/algo"
	"testing"
	"time"

	"github.com/kylelemons/godebug/pretty"
	"golang.org/x/net/context"
)

var midnight = time.Date(2006, 1, 2, 0, 0, 0, 0, time.UTC)

func TestAllShifts(t *testing.T) {
	ctx := newTestContext()
	ctxCancel, cancel := context.WithCancel(ctx)
	cancel()

	tests := []struct {
		name    string
		fail    bool
		ctx     context.Context
		rota    string
		rotaCfg *rotang.Configuration
		add     []rotang.ShiftEntry
	}{{
		name: "Canceled context",
		fail: true,
		ctx:  ctxCancel,
		rota: "test rota",
		rotaCfg: &rotang.Configuration{
			Config: rotang.Config{
				Name:        "test rota",
				Description: "Test",
			},
		},
	}, {
		name: "Success",
		ctx:  ctx,
		rota: "test rota",
		rotaCfg: &rotang.Configuration{
			Config: rotang.Config{
				Name:        "test rota",
				Description: "Test",
			},
		},
		add: []rotang.ShiftEntry{
			{
				Name:      "MTV Shift",
				StartTime: midnight,
				EndTime:   midnight.Add(8 * time.Hour),
			},
			{
				Name:      "MTV Shift",
				StartTime: midnight.Add(8 * time.Hour),
				EndTime:   midnight.Add(2 * 8 * time.Hour),
			},
			{
				Name:      "MTV Shift",
				StartTime: midnight.Add(2 * 8 * time.Hour),
				EndTime:   midnight.Add(3 * 8 * time.Hour),
			},
		},
	}, {
		name: "No shifts",
		fail: true,
		ctx:  ctx,
		rota: "test rota",
		rotaCfg: &rotang.Configuration{
			Config: rotang.Config{
				Name:        "test rota",
				Description: "Test",
			},
		},
	},
	}

	store := New(ctx)

	for _, tst := range tests {
		t.Run(tst.name, func(t *testing.T) {
			if err := store.CreateRotaConfig(ctx, tst.rotaCfg); err != nil {
				t.Fatalf("%s: store.CreateRotaConfig(ctx, _) failed: %v", tst.name, err)
			}
			defer store.DeleteRotaConfig(ctx, tst.rotaCfg.Config.Name)
			if tst.add != nil {
				if err := store.AddShifts(ctx, tst.rotaCfg.Config.Name, tst.add); err != nil {
					t.Fatalf("%s: store.AddShifts(ctx, %q, _) failed: %v", tst.name, tst.rotaCfg.Config.Name, err)
				}
				defer store.DeleteAllShifts(ctx, tst.rotaCfg.Config.Name)
			}

			shifts, err := store.AllShifts(ctx, tst.rotaCfg.Config.Name)
			if got, want := (err != nil), tst.fail; got != want {
				t.Fatalf("%s: store.AllShifts(ctx, %q) = %t want: %t, err: %v", tst.name, tst.rota, got, want, err)
			}
			if err != nil {
				return
			}

			if diff := pretty.Compare(tst.add, shifts); diff != "" {
				t.Fatalf("%s: store.UpdateShift(ctx, %q) differ -want +got, %s", tst.name, tst.rota, diff)
			}
		})
	}
}

func TestUpdateShift(t *testing.T) {
	ctx := newTestContext()
	ctxCancel, cancel := context.WithCancel(ctx)
	cancel()

	tests := []struct {
		name    string
		fail    bool
		ctx     context.Context
		rota    string
		entry   *rotang.ShiftEntry
		rotaCfg *rotang.Configuration
		add     []rotang.ShiftEntry
		want    []rotang.ShiftEntry
	}{{
		name: "Canceled context",
		fail: true,
		ctx:  ctxCancel,
		rota: "test rota",
		rotaCfg: &rotang.Configuration{
			Config: rotang.Config{
				Name:        "test rota",
				Description: "Test",
			},
		},
	}, {
		name: "Update entry",
		ctx:  ctx,
		rota: "test rota",
		entry: &rotang.ShiftEntry{
			Name:      "Modified Shift",
			StartTime: midnight.Add(8 * time.Hour),
			EndTime:   midnight.Add(2 * 8 * time.Hour),
		},
		rotaCfg: &rotang.Configuration{
			Config: rotang.Config{
				Name:        "test rota",
				Description: "Test",
			},
		},
		add: []rotang.ShiftEntry{
			{
				Name:      "MTV Shift",
				StartTime: midnight,
				EndTime:   midnight.Add(8 * time.Hour),
			},
			{
				Name:      "MTV Shift",
				StartTime: midnight.Add(8 * time.Hour),
				EndTime:   midnight.Add(2 * 8 * time.Hour),
			},
			{
				Name:      "MTV Shift",
				StartTime: midnight.Add(2 * 8 * time.Hour),
				EndTime:   midnight.Add(3 * 8 * time.Hour),
			},
		},
		want: []rotang.ShiftEntry{
			{
				Name:      "MTV Shift",
				StartTime: midnight,
				EndTime:   midnight.Add(8 * time.Hour),
			},
			{
				Name:      "Modified Shift",
				StartTime: midnight.Add(8 * time.Hour),
				EndTime:   midnight.Add(2 * 8 * time.Hour),
			},
			{
				Name:      "MTV Shift",
				StartTime: midnight.Add(2 * 8 * time.Hour),
				EndTime:   midnight.Add(3 * 8 * time.Hour),
			},
		},
	}, {
		name: "No shift entry",
		fail: true,
		ctx:  ctx,
		rota: "test rota",
		rotaCfg: &rotang.Configuration{
			Config: rotang.Config{
				Name:        "test rota",
				Description: "Test",
			},
		},
	}, {
		name: "Shift not found",
		fail: true,
		ctx:  ctx,
		rota: "test rota",
		entry: &rotang.ShiftEntry{
			Name:      "Modified Shift",
			StartTime: midnight,
			EndTime:   midnight.Add(8 * time.Hour),
		},
		rotaCfg: &rotang.Configuration{
			Config: rotang.Config{
				Name:        "test rota",
				Description: "Test",
			},
		},
		add: []rotang.ShiftEntry{
			{
				Name:      "MTV Shift",
				StartTime: midnight.Add(8 * time.Hour),
				EndTime:   midnight.Add(2 * 8 * time.Hour),
			},
			{
				Name:      "MTV Shift",
				StartTime: midnight.Add(2 * 8 * time.Hour),
				EndTime:   midnight.Add(3 * 8 * time.Hour),
			},
		},
	},
	}

	store := New(ctx)

	for _, tst := range tests {
		t.Run(tst.name, func(t *testing.T) {
			if err := store.CreateRotaConfig(ctx, tst.rotaCfg); err != nil {
				t.Fatalf("%s: store.CreateRotaConfig(ctx, _) failed: %v", tst.name, err)
			}
			defer store.DeleteRotaConfig(ctx, tst.rotaCfg.Config.Name)
			if tst.add != nil {
				if err := store.AddShifts(ctx, tst.rotaCfg.Config.Name, tst.add); err != nil {
					t.Fatalf("%s: store.AddShifts(ctx, %q, _) failed: %v", tst.name, tst.rotaCfg.Config.Name, err)
				}
				defer store.DeleteAllShifts(ctx, tst.rotaCfg.Config.Name)
			}

			err := store.UpdateShift(tst.ctx, tst.rota, tst.entry)
			if got, want := (err != nil), tst.fail; got != want {
				t.Fatalf("%s: store.ModifyShift(ctx, %q, _) = %t want: %t, err: %v", tst.name, tst.rota, got, want, err)
			}
			if err != nil {
				return
			}
			shifts, err := store.AllShifts(ctx, tst.rotaCfg.Config.Name)
			if err != nil {
				t.Fatalf("%s: store.AllShifts(ctx, %q) failed: %v", tst.name, tst.rotaCfg.Config.Name, err)
			}

			if diff := pretty.Compare(tst.want, shifts); diff != "" {
				t.Fatalf("%s: store.UpdateShift(ctx, %q, _) differ -want +got, %s", tst.name, tst.rota, diff)
			}
		})
	}
}

func TestDeleteShift(t *testing.T) {
	ctx := newTestContext()
	ctxCancel, cancel := context.WithCancel(ctx)
	cancel()

	tests := []struct {
		name    string
		fail    bool
		ctx     context.Context
		rota    string
		time    time.Time
		rotaCfg *rotang.Configuration
		add     []rotang.ShiftEntry
		want    []rotang.ShiftEntry
	}{{
		name: "Canceled context",
		fail: true,
		ctx:  ctxCancel,
		rota: "test rota",
		rotaCfg: &rotang.Configuration{
			Config: rotang.Config{
				Name:        "test rota",
				Description: "Test",
			},
		},
	}, {
		name: "Delete entry",
		ctx:  ctx,
		rota: "test rota",
		time: midnight.Add(8 * time.Hour),
		rotaCfg: &rotang.Configuration{
			Config: rotang.Config{
				Name:        "test rota",
				Description: "Test",
			},
		},
		add: []rotang.ShiftEntry{
			{
				Name:      "MTV Shift",
				StartTime: midnight,
				EndTime:   midnight.Add(8 * time.Hour),
			},
			{
				Name:      "MTV Shift",
				StartTime: midnight.Add(8 * time.Hour),
				EndTime:   midnight.Add(2 * 8 * time.Hour),
			},
			{
				Name:      "MTV Shift",
				StartTime: midnight.Add(2 * 8 * time.Hour),
				EndTime:   midnight.Add(3 * 8 * time.Hour),
			},
		},
		want: []rotang.ShiftEntry{
			{
				Name:      "MTV Shift",
				StartTime: midnight,
				EndTime:   midnight.Add(8 * time.Hour),
			},
			{
				Name:      "MTV Shift",
				StartTime: midnight.Add(2 * 8 * time.Hour),
				EndTime:   midnight.Add(3 * 8 * time.Hour),
			},
		},
	},
	}

	store := New(ctx)

	for _, tst := range tests {
		t.Run(tst.name, func(t *testing.T) {
			if err := store.CreateRotaConfig(ctx, tst.rotaCfg); err != nil {
				t.Fatalf("%s: store.CreateRotaConfig(ctx, _) failed: %v", tst.name, err)
			}
			defer store.DeleteRotaConfig(ctx, tst.rotaCfg.Config.Name)
			if tst.add != nil {
				if err := store.AddShifts(ctx, tst.rotaCfg.Config.Name, tst.add); err != nil {
					t.Fatalf("%s: store.AddShifts(ctx, %q, _) failed: %v", tst.name, tst.rotaCfg.Config.Name, err)
				}
				defer store.DeleteAllShifts(ctx, tst.rotaCfg.Config.Name)
			}

			err := store.DeleteShift(tst.ctx, tst.rota, tst.time)
			if got, want := (err != nil), tst.fail; got != want {
				t.Fatalf("%s: store.DeleteShift(ctx, %q, %v) = %t want: %t, err: %v", tst.name, tst.rota, tst.time, got, want, err)
			}
			if err != nil {
				return
			}
			shifts, err := store.AllShifts(ctx, tst.rotaCfg.Config.Name)
			if err != nil {
				t.Fatalf("%s: store.AllShifts(ctx, %q) failed: %v", tst.name, tst.rotaCfg.Config.Name, err)
			}

			if diff := pretty.Compare(tst.want, shifts); diff != "" {
				t.Fatalf("%s: store.DeleteShift(ctx, %q, %v) differ -want +got, %s", tst.name, tst.rota, tst.time, diff)
			}
		})
	}
}

func TestShift(t *testing.T) {
	ctx := newTestContext()
	ctxCancel, cancel := context.WithCancel(ctx)
	cancel()

	tests := []struct {
		name       string
		fail       bool
		ctx        context.Context
		rota       string
		time       time.Time
		rotaCfg    *rotang.Configuration
		memberPool []rotang.Member
		add        []rotang.ShiftEntry
		want       rotang.ShiftEntry
	}{{
		name: "Canceled context",
		fail: true,
		ctx:  ctxCancel,
		time: midnight,
		rota: "test rota",
		rotaCfg: &rotang.Configuration{
			Config: rotang.Config{
				Description: "Test",
				Name:        "test rota",
			},
		},
	}, {
		name: "Shift Found",
		ctx:  ctx,
		rota: "test rota",
		time: midnight,
		rotaCfg: &rotang.Configuration{
			Config: rotang.Config{
				Description: "Test",
				Name:        "test rota",
			},
		},
		add: []rotang.ShiftEntry{
			{
				Name:      "MTV Shift",
				StartTime: midnight,
				EndTime:   midnight.Add(8 * time.Hour),
			},
			{
				Name:      "MTV Shift",
				StartTime: midnight.Add(8 * time.Hour),
				EndTime:   midnight.Add(2 * 8 * time.Hour),
			},
		},
		want: rotang.ShiftEntry{
			Name:      "MTV Shift",
			StartTime: midnight,
			EndTime:   midnight.Add(8 * time.Hour),
		},
	}, {
		name: "Shift Does not exist",
		ctx:  ctx,
		fail: true,
		rota: "test rota",
		time: midnight,
		rotaCfg: &rotang.Configuration{
			Config: rotang.Config{
				Description: "Test",
				Name:        "test rota",
			},
		},
		add: []rotang.ShiftEntry{
			{
				Name:      "MTV Shift",
				StartTime: midnight.Add(8 * time.Hour),
				EndTime:   midnight.Add(2 * 8 * time.Hour),
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
			if err := store.AddShifts(ctx, tst.rotaCfg.Config.Name, tst.add); err != nil {
				t.Fatalf("%s: store.AddShifts(_, _) failed: %v", tst.name, err)
			}
			defer store.DeleteAllShifts(ctx, tst.rota)

			shift, err := store.Shift(tst.ctx, tst.rota, tst.time)
			if got, want := (err != nil), tst.fail; got != want {
				t.Fatalf("%s: store.Shift(ctx, %q, %v) = %t want: %t, err: %v", tst.name, tst.rota, tst.time, got, want, err)
			}
			if err != nil {
				return
			}
			if diff := pretty.Compare(tst.want, shift); diff != "" {
				t.Fatalf("%s: store.Shift(ctx, %q, %v) differs -want +got, %s", tst.name, tst.rota, tst.time, diff)
			}
		})
	}
}

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
		name: "Shift with no member",
		fail: true,
		rota: "test rota",
		ctx:  ctx,
		rotaCfg: &rotang.Configuration{
			Config: rotang.Config{
				Description: "Test",
				Name:        "test rota",
				Shifts: rotang.ShiftConfig{
					ShiftMembers: 0,
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

func TestOncall(t *testing.T) {
	ctx := newTestContext()
	ctxCancel, cancel := context.WithCancel(ctx)
	cancel()

	tests := []struct {
		name       string
		fail       bool
		ctx        context.Context
		rota       string
		nrShifts   int
		rotaCfg    *rotang.Configuration
		memberPool []rotang.Member
		time       time.Time
		want       []rotang.ShiftMember
	}{{
		name: "Canceled context",
		rota: "test rota",
		fail: true,
		rotaCfg: &rotang.Configuration{
			Config: rotang.Config{
				Description: "Test",
				Name:        "test rota",
			},
		},
		time: time.Now(),
		ctx:  ctxCancel,
	}, {
		name: "No shifts",
		rota: "test rota",
		ctx:  ctx,
		fail: true,
		rotaCfg: &rotang.Configuration{
			Config: rotang.Config{
				Description: "Test",
				Name:        "test rota",
			},
		},
		time: time.Now(),
	}, {
		name: "Rota not exist",
		rota: "Mismatch rota",
		ctx:  ctx,
		fail: true,
		rotaCfg: &rotang.Configuration{
			Config: rotang.Config{
				Description: "Test",
				Name:        "test rota",
			},
		},
		time: time.Now(),
	}, {
		name:     "Someone oncall",
		rota:     "test rota",
		ctx:      ctx,
		nrShifts: 1,
		time:     midnight.Add(4 * time.Hour),
		rotaCfg: &rotang.Configuration{
			Config: rotang.Config{
				Description: "Test",
				Name:        "test rota",
				Shifts: rotang.ShiftConfig{
					ShiftMembers: 1,
					StartTime:    midnight,
					Length:       1,
					Shifts: []rotang.Shift{
						{
							Name:     "MTV All Day",
							Duration: 24 * time.Hour,
						},
					},
				},
			},
			Members: []rotang.ShiftMember{
				{
					Email:     "oncaller@oncall.com",
					ShiftName: "MTV All Day",
				},
			},
		},
		memberPool: []rotang.Member{
			{
				Email: "oncaller@oncall.com",
			},
		},
		want: []rotang.ShiftMember{
			{
				ShiftName: "MTV All Day",
				Email:     "oncaller@oncall.com",
			},
		},
	}, {
		name:     "Nobody oncall",
		rota:     "test rota",
		ctx:      ctx,
		time:     midnight.Add(4 * time.Hour),
		nrShifts: 2,
		rotaCfg: &rotang.Configuration{
			Config: rotang.Config{
				Description: "Test",
				Name:        "test rota",
				Shifts: rotang.ShiftConfig{
					ShiftMembers: 0,
					Length:       2,
					Shifts: []rotang.Shift{
						{
							Name:     "MTV All Day",
							Duration: 24 * time.Hour,
						},
					},
				},
			},
		},
	}, {
		name:     "Multiple oncallers",
		rota:     "test rota",
		ctx:      ctx,
		nrShifts: 2,
		time:     midnight.Add(4 * time.Hour),
		rotaCfg: &rotang.Configuration{
			Config: rotang.Config{
				Description: "Test",
				Name:        "test rota",
				Shifts: rotang.ShiftConfig{
					ShiftMembers: 2,
					Length:       2,
					StartTime:    midnight,
					Shifts: []rotang.Shift{
						{
							Name:     "MTV All day",
							Duration: 24 * time.Hour,
						},
					},
				},
			},
			Members: []rotang.ShiftMember{
				{
					Email:     "oncaller@oncall.com",
					ShiftName: "MTV All day",
				},
				{
					Email:     "secondary@oncall.com",
					ShiftName: "MTV All day",
				},
			},
		},
		memberPool: []rotang.Member{
			{
				Email: "oncaller@oncall.com",
			},
			{
				Email: "secondary@oncall.com",
			},
		},
		want: []rotang.ShiftMember{
			{
				ShiftName: "MTV All day",
				Email:     "oncaller@oncall.com",
			},
			{
				ShiftName: "MTV All day",
				Email:     "secondary@oncall.com",
			},
		},
	}, {
		name:     "Multiple shifts",
		rota:     "test rota",
		ctx:      ctx,
		time:     midnight.Add(12 * time.Hour),
		nrShifts: 4,
		rotaCfg: &rotang.Configuration{
			Config: rotang.Config{
				Description: "Test",
				Name:        "test rota",
				Shifts: rotang.ShiftConfig{
					StartTime:    midnight,
					ShiftMembers: 1,
					Length:       2,
					Shifts: []rotang.Shift{
						{
							Name:     "MTV Shift",
							Duration: 8 * time.Hour,
						},
						{
							Name:     "SYD Shift",
							Duration: 8 * time.Hour,
						},
						{
							Name:     "EU Shift",
							Duration: 8 * time.Hour,
						},
					},
				},
			},
			Members: []rotang.ShiftMember{
				{
					Email:     "mtv@oncall.com",
					ShiftName: "MTV Shift",
				},
				{
					Email:     "syd@oncall.com",
					ShiftName: "SYD Shift",
				},
				{
					Email:     "eu@oncall.com",
					ShiftName: "EU Shift",
				},
			},
		},
		memberPool: []rotang.Member{
			{
				Email: "mtv@oncall.com",
			},
			{
				Email: "syd@oncall.com",
			},
			{
				Email: "eu@oncall.com",
			},
		},
		want: []rotang.ShiftMember{
			{
				Email:     "syd@oncall.com",
				ShiftName: "SYD Shift",
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
			if err := store.AddShifts(ctx, tst.rotaCfg.Config.Name, algo.MakeShifts(tst.rotaCfg, midnight, algo.HandleShiftMembers(tst.rotaCfg, tst.memberPool), tst.nrShifts)); err != nil {
				t.Fatalf("%s: store.AddShifts(_, _) failed: %v", tst.name, err)
			}
			defer store.DeleteAllShifts(ctx, tst.rota)

			oncall, err := store.Oncall(tst.ctx, tst.time, tst.rota)
			if got, want := (err != nil), tst.fail; got != want {
				t.Fatalf("%s: store.Oncall(ctx, %v, %q) = %t want: %t, err: %v", tst.name, tst.time, tst.rota, got, want, err)
			}
			if err != nil {
				return
			}

			if diff := pretty.Compare(tst.want, oncall.OnCall); diff != "" {
				t.Fatalf("%s: store.Oncall(ctx, %v, %q) differs -want +got, %s", tst.name, tst.time, tst.rota, diff)
			}
		})
	}
}
