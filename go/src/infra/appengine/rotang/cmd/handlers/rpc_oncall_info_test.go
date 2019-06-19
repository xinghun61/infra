package handlers

import (
	"context"
	"infra/appengine/rotang"
	"testing"
	"time"

	"github.com/golang/protobuf/proto"
	"github.com/kylelemons/godebug/pretty"
	"go.chromium.org/luci/common/clock"
	"go.chromium.org/luci/common/clock/testclock"

	apb "infra/appengine/rotang/proto/rotangapi"
)

func TestRPCShifts(t *testing.T) {
	ctx := newTestContext()

	tests := []struct {
		name    string
		fail    bool
		ctx     context.Context
		in      string
		cfgs    []*rotang.Configuration
		members []rotang.Member
		shifts  []rotang.ShiftEntry
		time    time.Time
		want    string
	}{{
		name: "Success",
		in: `
			name: "Test Rota"
			start: {
				seconds: 1143849600,
			},
			end:   {
				seconds: 1144022400,
			},
		`,
		time: midnight,
		ctx:  ctx,
		cfgs: []*rotang.Configuration{
			{
				Config: rotang.Config{
					Name: "Test Rota",
					Shifts: rotang.ShiftConfig{
						Generator: "Fair",
						Shifts: []rotang.Shift{
							{
								Name: "MTV All Day",
							},
						},
					},
				},
				Members: []rotang.ShiftMember{
					{
						Email:     "mtv1@oncall.com",
						ShiftName: "MTV All Day",
					}, {
						Email:     "mtv2@oncall.com",
						ShiftName: "MTV All Day",
					},
				},
			},
		},
		members: []rotang.Member{
			{
				Email: "mtv1@oncall.com",
				Name:  "Mtv1 Mtvsson",
				TZ:    *time.UTC,
			}, {
				Email: "mtv2@oncall.com",
				Name:  "Mtv2 Mtvsson",
				TZ:    *time.UTC,
			},
		},
		shifts: []rotang.ShiftEntry{
			{
				Name:      "MTV All Day",
				StartTime: midnight.Add(-1 * fullDay),
				EndTime:   midnight.Add(fullDay),
				OnCall: []rotang.ShiftMember{
					{
						Email:     "mtv1@oncall.com",
						ShiftName: "MTV All Day",
					},
				},
			},
		},
		want: `
		shifts: <
			name: "MTV All Day"
			oncallers: <
					email: "mtv1@oncall.com",
					name: "Mtv1 Mtvsson",
					tz: "UTC",
			>,
			start: {
				seconds: 1143849600,
			},
			end: {
				seconds: 1144022400,
			},
    >
		`,
	}, {
		name: "No rota name",
		fail: true,
		ctx:  ctx,
	}, {
		name: "Non existing rota",
		fail: true,
		ctx:  ctx,
		in:   `name: "Non Exist"`,
	}, {
		name: "No Shifts",
		in: `
			name: "Test Rota"
			start: {
				seconds: 1143849600,
			},
			end:   {
				seconds: 1144022400,
			},
		`,
		time: midnight,
		ctx:  ctx,
		cfgs: []*rotang.Configuration{
			{
				Config: rotang.Config{
					Name: "Test Rota",
					Shifts: rotang.ShiftConfig{
						Generator: "Fair",
						Shifts: []rotang.Shift{
							{
								Name: "MTV All Day",
							},
						},
					},
				},
				Members: []rotang.ShiftMember{
					{
						Email:     "mtv1@oncall.com",
						ShiftName: "MTV All Day",
					}, {
						Email:     "mtv2@oncall.com",
						ShiftName: "MTV All Day",
					},
				},
			},
		},
		members: []rotang.Member{
			{
				Email: "mtv1@oncall.com",
				Name:  "Mtv1 Mtvsson",
				TZ:    *time.UTC,
			}, {
				Email: "mtv2@oncall.com",
				Name:  "Mtv2 Mtvsson",
				TZ:    *time.UTC,
			},
		},
		shifts: []rotang.ShiftEntry{
			{
				Name:      "MTV All Day",
				StartTime: midnight.Add(2 * fullDay),
				EndTime:   midnight.Add(4 * fullDay),
				OnCall: []rotang.ShiftMember{
					{
						Email:     "mtv1@oncall.com",
						ShiftName: "MTV All Day",
					},
				},
			},
		},
	}}

	h := testSetup(t)

	for _, tst := range tests {
		t.Run(tst.name, func(t *testing.T) {
			for _, m := range tst.members {
				if err := h.memberStore(ctx).CreateMember(ctx, &m); err != nil {
					t.Fatalf("%s: CreateMember(ctx, _) failed: %v", tst.name, err)
				}
				defer h.memberStore(ctx).DeleteMember(ctx, m.Email)
			}
			for _, c := range tst.cfgs {
				if err := h.configStore(ctx).CreateRotaConfig(ctx, c); err != nil {
					t.Fatalf("%s: CreateRotaconfig(ctx, _) failed: %v", tst.name, err)
				}
				defer h.configStore(ctx).DeleteRotaConfig(ctx, c.Config.Name)
				if err := h.shiftStore(ctx).AddShifts(ctx, c.Config.Name, tst.shifts); err != nil {
					t.Fatalf("%s: AddShifts(ctx, %q, _) failed: %v", tst.name, c.Config.Name, err)
				}
				defer h.shiftStore(ctx).DeleteAllShifts(ctx, c.Config.Name)
			}

			tst.ctx = clock.Set(tst.ctx, testclock.New(tst.time))

			var inPB apb.ShiftsRequest
			if err := proto.UnmarshalText(tst.in, &inPB); err != nil {
				t.Fatalf("%s: proto.UnmarshalText(_, _) failed: %v", tst.name, err)
			}

			var wantPB apb.ShiftsResponse
			if err := proto.UnmarshalText(tst.want, &wantPB); err != nil {
				t.Fatalf("%s: proto.UnmarshalText(_, _) failed: %v", tst.name, err)
			}

			res, err := h.Shifts(tst.ctx, &inPB)
			if got, want := (err != nil), tst.fail; got != want {
				t.Fatalf("%s: h.Oncall(ctx, _) = %t want: %t, err: %v", tst.name, got, want, err)
			}

			if err != nil {
				return
			}

			if diff := pretty.Compare(wantPB, res); diff != "" {
				t.Fatalf("%s: h.Oncall(ctx, _) differ -want +got: %s", tst.name, diff)
			}
		})
	}
}

func TestRPCOncall(t *testing.T) {
	ctx := newTestContext()

	tests := []struct {
		name    string
		fail    bool
		ctx     context.Context
		in      string
		cfgs    []*rotang.Configuration
		members []rotang.Member
		shifts  []rotang.ShiftEntry
		time    time.Time
		want    string
	}{{
		name: "Success",
		in:   `name: "Test Rota"`,
		time: midnight,
		ctx:  ctx,
		cfgs: []*rotang.Configuration{
			{
				Config: rotang.Config{
					Name: "Test Rota",
					Shifts: rotang.ShiftConfig{
						Generator: "Fair",
						Shifts: []rotang.Shift{
							{
								Name: "MTV All Day",
							},
						},
					},
				},
				Members: []rotang.ShiftMember{
					{
						Email:     "mtv1@oncall.com",
						ShiftName: "MTV All Day",
					}, {
						Email:     "mtv2@oncall.com",
						ShiftName: "MTV All Day",
					},
				},
			},
		},
		members: []rotang.Member{
			{
				Email: "mtv1@oncall.com",
				Name:  "Mtv1 Mtvsson",
				TZ:    *time.UTC,
			}, {
				Email: "mtv2@oncall.com",
				Name:  "Mtv2 Mtvsson",
				TZ:    *time.UTC,
			},
		},
		shifts: []rotang.ShiftEntry{
			{
				Name:      "MTV All Day",
				StartTime: midnight.Add(-1 * fullDay),
				EndTime:   midnight.Add(fullDay),
				OnCall: []rotang.ShiftMember{
					{
						Email:     "mtv1@oncall.com",
						ShiftName: "MTV All Day",
					},
				},
			},
		},
		want: `shift: {
				name: "MTV All Day",
				oncallers: <
					email: "mtv1@oncall.com",
					name: "Mtv1 Mtvsson",
					tz: "UTC",
				>,
				start: {
					seconds: 1143849600,
				},
				end: {
					seconds: 1144022400,
				},
			}`,
	}, {
		name: "No rota name",
		fail: true,
		ctx:  ctx,
	}, {
		name: "TZConsider generator",
		in:   `name: "Test Rota"`,
		time: midnight,
		ctx:  ctx,
		cfgs: []*rotang.Configuration{
			{
				Config: rotang.Config{
					Name: "Test Rota",
					Shifts: rotang.ShiftConfig{
						Generator: "TZRecent",
						Shifts: []rotang.Shift{
							{
								Name: "MTV All Day",
							},
						},
					},
				},
				Members: []rotang.ShiftMember{
					{
						Email:     "mtv1@oncall.com",
						ShiftName: "MTV All Day",
					}, {
						Email:     "mtv2@oncall.com",
						ShiftName: "MTV All Day",
					},
				},
			},
		},
		members: []rotang.Member{
			{
				Email: "mtv1@oncall.com",
				Name:  "Mtv1 Mtvsson",
				TZ:    *time.UTC,
			}, {
				Email: "mtv2@oncall.com",
				Name:  "Mtv2 Mtvsson",
				TZ:    *time.UTC,
			},
		},
		shifts: []rotang.ShiftEntry{
			{
				Name:      "MTV All Day",
				StartTime: midnight.Add(-1 * fullDay),
				EndTime:   midnight.Add(fullDay),
				OnCall: []rotang.ShiftMember{
					{
						Email:     "mtv1@oncall.com",
						ShiftName: "MTV All Day",
					},
				},
			},
		},
		want: `shift: {
				name: "MTV All Day",
				oncallers: <
					email: "mtv1@oncall.com",
					name: "Mtv1 Mtvsson",
					tz: "UTC",
				>,
				start: {
					seconds: 1143849600,
				},
				end: {
					seconds: 1144022400,
				},
			}
			tz_consider: true`,
	}, {
		name: "Nobody OnCall",
		in:   `name: "Test Rota"`,
		time: midnight,
		ctx:  ctx,
		cfgs: []*rotang.Configuration{
			{
				Config: rotang.Config{
					Name: "Test Rota",
					Shifts: rotang.ShiftConfig{
						Generator: "TZRecent",
						Shifts: []rotang.Shift{
							{
								Name: "MTV All Day",
							},
						},
					},
				},
				Members: []rotang.ShiftMember{
					{
						Email:     "mtv1@oncall.com",
						ShiftName: "MTV All Day",
					}, {
						Email:     "mtv2@oncall.com",
						ShiftName: "MTV All Day",
					},
				},
			},
		},
		members: []rotang.Member{
			{
				Email: "mtv1@oncall.com",
				Name:  "Mtv1 Mtvsson",
				TZ:    *time.UTC,
			}, {
				Email: "mtv2@oncall.com",
				Name:  "Mtv2 Mtvsson",
				TZ:    *time.UTC,
			},
		},
		shifts: []rotang.ShiftEntry{
			{
				Name:      "MTV All Day",
				StartTime: midnight.Add(fullDay),
				EndTime:   midnight.Add(2 * fullDay),
				OnCall: []rotang.ShiftMember{
					{
						Email:     "mtv1@oncall.com",
						ShiftName: "MTV All Day",
					},
				},
			},
		},
		want: `tz_consider: true`,
	}}

	h := testSetup(t)

	for _, tst := range tests {
		t.Run(tst.name, func(t *testing.T) {
			for _, m := range tst.members {
				if err := h.memberStore(ctx).CreateMember(ctx, &m); err != nil {
					t.Fatalf("%s: CreateMember(ctx, _) failed: %v", tst.name, err)
				}
				defer h.memberStore(ctx).DeleteMember(ctx, m.Email)
			}
			for _, c := range tst.cfgs {
				if err := h.configStore(ctx).CreateRotaConfig(ctx, c); err != nil {
					t.Fatalf("%s: CreateRotaconfig(ctx, _) failed: %v", tst.name, err)
				}
				defer h.configStore(ctx).DeleteRotaConfig(ctx, c.Config.Name)
				if err := h.shiftStore(ctx).AddShifts(ctx, c.Config.Name, tst.shifts); err != nil {
					t.Fatalf("%s: AddShifts(ctx, %q, _) failed: %v", tst.name, c.Config.Name, err)
				}
				defer h.shiftStore(ctx).DeleteAllShifts(ctx, c.Config.Name)
			}

			tst.ctx = clock.Set(tst.ctx, testclock.New(tst.time))

			var inPB apb.OncallRequest
			if err := proto.UnmarshalText(tst.in, &inPB); err != nil {
				t.Fatalf("%s: proto.UnmarshalText(_, _) failed: %v", tst.name, err)
			}

			var wantPB apb.OncallResponse
			if err := proto.UnmarshalText(tst.want, &wantPB); err != nil {
				t.Fatalf("%s: proto.UnmarshalText(_, _) failed: %v", tst.name, err)
			}

			res, err := h.Oncall(tst.ctx, &inPB)
			if got, want := (err != nil), tst.fail; got != want {
				t.Fatalf("%s: h.Oncall(ctx, _) = %t want: %t, err: %v", tst.name, got, want, err)
			}

			if err != nil {
				return
			}

			if diff := pretty.Compare(wantPB, res); diff != "" {
				t.Fatalf("%s: h.Oncall(ctx, _) differ -want +got: %s", tst.name, diff)
			}
		})
	}
}

func TestRPCList(t *testing.T) {
	ctx := newTestContext()

	tests := []struct {
		name    string
		fail    bool
		ctx     context.Context
		in      string
		cfgs    []*rotang.Configuration
		members []rotang.Member
		time    time.Time
		want    string
	}{{
		name: "Success",
		time: midnight,
		ctx:  ctx,
		cfgs: []*rotang.Configuration{
			{
				Config: rotang.Config{
					Name: "Test Rota",
					Shifts: rotang.ShiftConfig{
						Generator: "Fair",
						Shifts: []rotang.Shift{
							{
								Name: "MTV All Day",
							},
						},
					},
				},
				Members: []rotang.ShiftMember{
					{
						Email:     "mtv1@oncall.com",
						ShiftName: "MTV All Day",
					}, {
						Email:     "mtv2@oncall.com",
						ShiftName: "MTV All Day",
					},
				},
			},
		},
		members: []rotang.Member{
			{
				Email: "mtv1@oncall.com",
				Name:  "Mtv1 Mtvsson",
			}, {
				Email: "mtv2@oncall.com",
				Name:  "Mtv2 Mtvsson",
			},
		},
		want: `
		rotations: <
			name: "Test Rota"
    >
		`,
	}, {
		name: "No rotations",
		fail: true,
		ctx:  ctx,
	}}

	h := testSetup(t)

	for _, tst := range tests {
		t.Run(tst.name, func(t *testing.T) {
			for _, m := range tst.members {
				if err := h.memberStore(ctx).CreateMember(ctx, &m); err != nil {
					t.Fatalf("%s: CreateMember(ctx, _) failed: %v", tst.name, err)
				}
				defer h.memberStore(ctx).DeleteMember(ctx, m.Email)
			}
			for _, c := range tst.cfgs {
				if err := h.configStore(ctx).CreateRotaConfig(ctx, c); err != nil {
					t.Fatalf("%s: CreateRotaconfig(ctx, _) failed: %v", tst.name, err)
				}
				defer h.configStore(ctx).DeleteRotaConfig(ctx, c.Config.Name)
			}

			tst.ctx = clock.Set(tst.ctx, testclock.New(tst.time))

			var inPB apb.ListRotationsRequest
			if err := proto.UnmarshalText(tst.in, &inPB); err != nil {
				t.Fatalf("%s: proto.UnmarshalText(_, _) failed: %v", tst.name, err)
			}

			var wantPB apb.ListRotationsResponse
			if err := proto.UnmarshalText(tst.want, &wantPB); err != nil {
				t.Fatalf("%s: proto.UnmarshalText(_, _) failed: %v", tst.name, err)
			}

			res, err := h.ListRotations(tst.ctx, &inPB)
			if got, want := (err != nil), tst.fail; got != want {
				t.Fatalf("%s: h.Oncall(ctx, _) = %t want: %t, err: %v", tst.name, got, want, err)
			}

			if err != nil {
				return
			}

			if diff := pretty.Compare(wantPB, res); diff != "" {
				t.Fatalf("%s: h.Oncall(ctx, _) differ -want +got: %s", tst.name, diff)
			}
		})
	}
}
