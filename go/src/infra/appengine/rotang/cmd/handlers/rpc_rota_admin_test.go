package handlers

import (
	"context"
	"infra/appengine/rotang"
	"testing"

	"github.com/golang/protobuf/proto"
	"github.com/kylelemons/godebug/pretty"
	"go.chromium.org/luci/auth/identity"
	"go.chromium.org/luci/server/auth"
	"go.chromium.org/luci/server/auth/authtest"

	apb "infra/appengine/rotang/proto/rotangapi"
)

func TestRPCCreateExternal(t *testing.T) {
	ctx := newTestContext()

	tests := []struct {
		name string
		fail bool
		ctx  context.Context
		in   string
		cfgs []*rotang.Configuration
		want string
	}{{
		name: "Success",
		in: `
			name: "Not Test Rota",
			calendar: "nonExists"
			owners_emails: [
				"owner1@google.com",
				"owner2@google.com"
			],
			description: "External Rotation Test",
			match: "Not Test Rota:",
		`,
		ctx: ctx,
	}, {
		name: "No rota name",
		fail: true,
		ctx:  ctx,
		in: `
			calendar: "nonExists"
			owners_emails: [
				"owner1@google.com",
				"owner2@google.com"
			],
			description: "External Rotation Test",
			match: "Not Test Rota:",
		`,
	}, {
		name: "No calendar ID",
		fail: true,
		ctx:  ctx,
		in: `
			name: "Not Test Rota",
			owners_emails: [
				"owner1@google.com",
				"owner2@google.com"
			],
			description: "External Rotation Test",
			match: "Not Test Rota:",
		`,
	}, {
		name: "No owners",
		fail: true,
		ctx:  ctx,
		in: `
			name: "Not Test Rota",
			calendar: "nonExists"
			description: "External Rotation Test",
			match: "Not Test Rota:",
		`,
	}, {
		name: "No match",
		fail: true,
		ctx:  ctx,
		in: `
			name: "Not Test Rota",
			calendar: "nonExists"
			owners_emails: [
				"owner1@google.com",
				"owner2@google.com"
			],
			description: "External Rotation Test",
		`,
	}, {
		name: "Rota Already exists",
		fail: true,
		in: `
			name: "Already Exists Rota",
			calendar: "nonExists"
			owners_emails: [
				"owner1@google.com",
				"owner2@google.com"
			],
			description: "External Rotation Test",
			match: "Not Test Rota:",
		`,
		ctx: ctx,
		cfgs: []*rotang.Configuration{
			{
				Config: rotang.Config{
					Name: "Already Exists Rota",
					Shifts: rotang.ShiftConfig{
						Generator: "Fair",
						Shifts: []rotang.Shift{
							{
								Name: "MTV All Day",
							},
						},
					},
				},
			},
		},
	}, {
		name: "Invalid e-mail address",
		fail: true,
		in: `
			name: "Not Test Rota",
			calendar: "nonExists"
			owners_emails: [
				"owner1@google.com",
				"owner2@google.not-an-email"
			],
			description: "External Rotation Test",
			match: "Not Test Rota:",
		`,
		ctx: ctx,
	},
	}

	h := testSetup(t)

	for _, tst := range tests {
		t.Run(tst.name, func(t *testing.T) {
			for _, c := range tst.cfgs {
				if err := h.configStore(ctx).CreateRotaConfig(ctx, c); err != nil {
					t.Fatalf("%s: CreateRotaconfig(ctx, _) failed: %v", tst.name, err)
				}
				defer h.configStore(ctx).DeleteRotaConfig(ctx, c.Config.Name)
			}

			var inPB apb.CreateExternalRequest
			if err := proto.UnmarshalText(tst.in, &inPB); err != nil {
				t.Fatalf("%s: proto.UnmarshalText(_, _) failed: %v", tst.name, err)
			}

			var wantPB apb.CreateExternalResponse
			if err := proto.UnmarshalText(tst.want, &wantPB); err != nil {
				t.Fatalf("%s: proto.UnmarshalText(_, _) failed: %v", tst.name, err)
			}

			res, err := h.CreateExternal(tst.ctx, &inPB)
			if got, want := (err != nil), tst.fail; got != want {
				t.Fatalf("%s: h.CreateExternal(ctx, _) = %t want: %t, err: %v", tst.name, got, want, err)
			}

			if err != nil {
				return
			}

			if diff := pretty.Compare(wantPB, res); diff != "" {
				t.Fatalf("%s: h.DeleteExternal(ctx, _) differ -want +got: %s", tst.name, diff)
			}
		})
	}
}

func TestRPCDeleteExternal(t *testing.T) {
	ctx := newTestContext()

	tests := []struct {
		name string
		fail bool
		ctx  context.Context
		in   string
		user string
		cfgs []*rotang.Configuration
		want string
	}{{
		name: "Success",
		in: `
			name: "Test Rota",
		`,
		ctx:  ctx,
		user: "owner2@owner.com",
		cfgs: []*rotang.Configuration{
			{
				Config: rotang.Config{
					Name: "Test Rota",
					Owners: []string{
						"owner1@owner.com",
						"owner2@owner.com",
					},
					Shifts: rotang.ShiftConfig{
						Generator: "Fair",
						Shifts: []rotang.Shift{
							{
								Name: "MTV All Day",
							},
						},
					},
				},
			},
		},
	}, {
		name: "Not Owner",
		fail: true,
		in: `
			name: "Test Rota",
		`,
		ctx: ctx,
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
			},
		},
	}, {
		name: "Rota not exist",
		fail: true,
		in: `
			name: "Test Rota",
		`,
		ctx:  ctx,
		user: "owner2@owner.com",
	}, {
		name: "No rota name",
		fail: true,
		ctx:  ctx,
	}}

	h := testSetup(t)

	for _, tst := range tests {
		t.Run(tst.name, func(t *testing.T) {
			for _, c := range tst.cfgs {
				if err := h.configStore(ctx).CreateRotaConfig(ctx, c); err != nil {
					t.Fatalf("%s: CreateRotaconfig(ctx, _) failed: %v", tst.name, err)
				}
				defer h.configStore(ctx).DeleteRotaConfig(ctx, c.Config.Name)
			}

			var inPB apb.DeleteExternalRequest
			if err := proto.UnmarshalText(tst.in, &inPB); err != nil {
				t.Fatalf("%s: proto.UnmarshalText(_, _) failed: %v", tst.name, err)
			}

			var wantPB apb.DeleteExternalResponse
			if err := proto.UnmarshalText(tst.want, &wantPB); err != nil {
				t.Fatalf("%s: proto.UnmarshalText(_, _) failed: %v", tst.name, err)
			}

			if tst.user != "" {
				tst.ctx = auth.WithState(tst.ctx, &authtest.FakeState{
					Identity: identity.Identity("user:" + tst.user),
				})
			}

			res, err := h.DeleteExternal(tst.ctx, &inPB)
			if got, want := (err != nil), tst.fail; got != want {
				t.Fatalf("%s: h.DeleteExternal(ctx, _) = %t want: %t, err: %v", tst.name, got, want, err)
			}

			if err != nil {
				return
			}

			if diff := pretty.Compare(wantPB, res); diff != "" {
				t.Fatalf("%s: h.DeleteExternal(ctx, _) differ -want +got: %s", tst.name, diff)
			}
		})
	}
}
