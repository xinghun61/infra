// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package handlers

import (
	"context"
	"infra/appengine/rotang"
	"infra/appengine/rotang/pkg/algo"
	"infra/appengine/rotang/pkg/datastore"
	"net/http"
	"net/http/httptest"
	"testing"

	"go.chromium.org/luci/auth/identity"
	"go.chromium.org/luci/server/auth"
	"go.chromium.org/luci/server/auth/authtest"
	"go.chromium.org/luci/server/router"
	"go.chromium.org/luci/server/templates"
)

func setupStoreHandlers(o *Options, sf func(context.Context) *datastore.Store) {
	o.MemberStore = func(ctx context.Context) rotang.MemberStorer {
		return sf(ctx)
	}
	o.ShiftStore = func(ctx context.Context) rotang.ShiftStorer {
		return sf(ctx)
	}
	o.ConfigStore = func(ctx context.Context) rotang.ConfigStorer {
		return sf(ctx)
	}
}

func TestHandleIndex(t *testing.T) {
	ctx := newTestContext()
	ctxCancel, cancel := context.WithCancel(ctx)
	cancel()

	tests := []struct {
		name       string
		fail       bool
		email      string
		ctx        *router.Context
		memberPool []rotang.Member
		rotas      []rotang.Configuration
	}{{
		name: "Failed context",
		fail: true,
		ctx: &router.Context{
			Context: ctxCancel,
			Writer:  httptest.NewRecorder(),
			Request: getRequest("/", ""),
		},
	},
		{
			name: "Index Success - No user",
			ctx: &router.Context{
				Context: ctx,
				Writer:  httptest.NewRecorder(),
				Request: getRequest("/", ""),
			},
		}, {
			name:  "Index Success - User, no rotas",
			email: "test@user.com",
			ctx: &router.Context{
				Context: ctx,
				Writer:  httptest.NewRecorder(),
				Request: getRequest("/", ""),
			},
		}, {
			name:  "Index Success - User in rota",
			email: "test@user.com",
			ctx: &router.Context{
				Context: ctx,
				Writer:  httptest.NewRecorder(),
				Request: getRequest("/", ""),
			},
			memberPool: []rotang.Member{
				{
					Name:  "Test User",
					Email: "test@user.com",
				},
			},
			rotas: []rotang.Configuration{
				{
					Config: rotang.Config{
						Description:    "Test description",
						Name:           "Another rotation",
						Calendar:       "testCalendarLink@testland.com",
						DaysToSchedule: 10,
						Email: rotang.Email{
							Subject: "Chrome OS build sheriff reminder",
							Body:    "Some reminder",
						},
						Shifts: rotang.ShiftConfig{
							ShiftMembers: 1,
						},
					},
					Members: []rotang.ShiftMember{
						{
							Email: "test@user.com",
						},
					},
				},
			},
		},
	}

	opts := Options{
		URL:        "http://localhost:8080",
		Generators: &algo.Generators{},
	}
	setupStoreHandlers(&opts, datastore.New)
	h, err := New(&opts)
	if err != nil {
		t.Fatalf("New failed: %v", err)
	}

	for _, tst := range tests {
		t.Run(tst.name, func(t *testing.T) {
			for _, m := range tst.memberPool {
				if err := h.memberStore(ctx).CreateMember(ctx, &m); err != nil {
					t.Fatalf("%s: s.CreateMember(_, _) failed: %v", tst.name, err)
				}
				defer h.memberStore(ctx).DeleteMember(ctx, m.Email)
			}
			for _, cfg := range tst.rotas {
				if err := h.configStore(ctx).CreateRotaConfig(ctx, &cfg); err != nil {
					t.Fatalf("%s: s.CreateRotaConfig(_, _) failed: %v", tst.name, err)
				}
				defer h.configStore(ctx).DeleteRotaConfig(ctx, cfg.Config.Name)
			}
			tst.ctx.Context = templates.Use(tst.ctx.Context, &templates.Bundle{
				Loader: templates.FileSystemLoader(templatesLocation),
			}, nil)
			if tst.email != "" {
				tst.ctx.Context = auth.WithState(tst.ctx.Context, &authtest.FakeState{
					Identity: identity.Identity("user:" + tst.email),
				})
			}
			h.HandleIndex(tst.ctx)

			recorder := tst.ctx.Writer.(*httptest.ResponseRecorder)
			if got, want := (recorder.Code != http.StatusOK), tst.fail; got != want {
				t.Fatalf("%s: HandleIndex() = %t want: %t, res: %v", tst.name, got, want, recorder.Body)
			}
		})
	}
}
