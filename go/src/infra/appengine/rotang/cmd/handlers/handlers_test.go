// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package handlers

import (
	"infra/appengine/rotang"
	"infra/appengine/rotang/pkg/algo"
	"infra/appengine/rotang/pkg/calendar"
	"infra/appengine/rotang/pkg/datastore"
	"net/http"
	"strconv"
	"testing"
	"time"

	"go.chromium.org/luci/appengine/gaetesting"
	"go.chromium.org/luci/server/router"
	"golang.org/x/net/context"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

const templatesLocation = "../app/templates"

func newTestContext() context.Context {
	ctx := gaetesting.TestingContext()
	datastore.TestTable(ctx)
	return ctx
}

func getRequest(url, email string) *http.Request {
	req, err := http.NewRequest("GET", url, nil)
	if err != nil {
		panic(err)
	}
	return req
}

func testSetup(t *testing.T) *State {
	t.Helper()
	// Sort out the generators.
	gs := algo.New()
	gs.Register(algo.NewLegacy())
	gs.Register(algo.NewFair())
	gs.Register(algo.NewRandomGen())

	fake := &fakeCal{}

	opts := Options{
		URL:         "http://localhost:8080",
		Generators:  gs,
		Calendar:    fake,
		MailSender:  &testableMail{},
		MailAddress: "admin@example.com",
		ProdENV:     "production",
	}
	setupStoreHandlers(&opts, datastore.New)
	h, err := New(&opts)
	if err != nil {
		t.Fatalf("New failed: %v", err)
	}
	return h
}

type fakeCal struct {
	ret      []rotang.ShiftEntry
	fail     bool
	changeID bool
	rotang.Calenderer
	id     int
	events map[time.Time]rotang.ShiftEntry
}

func (f *fakeCal) Events(_ *router.Context, _ *rotang.Configuration, _, _ time.Time) ([]rotang.ShiftEntry, error) {
	if f.fail {
		return nil, status.Errorf(codes.Internal, "fake is failing as requested")
	}
	return f.ret, nil
}

func (f *fakeCal) Event(_ *router.Context, _ *rotang.Configuration, shift *rotang.ShiftEntry) (*rotang.ShiftEntry, error) {
	if f.fail {
		return nil, status.Errorf(codes.Internal, "fake is failing as requested")
	}
	sp := f.events[shift.StartTime]
	if f.changeID {
		sp.EvtID = strconv.Itoa(f.id)
		f.id++
	}
	f.events[shift.StartTime] = sp
	return &sp, nil
}

func (f *fakeCal) Set(ret []rotang.ShiftEntry, fail, changeID bool, id int) {
	f.ret = ret
	f.fail = fail
	f.id = id
	f.changeID = changeID
}

func (f *fakeCal) CreateEvent(_ *router.Context, _ *rotang.Configuration, shifts []rotang.ShiftEntry) ([]rotang.ShiftEntry, error) {
	if f.fail {
		return nil, status.Errorf(codes.Internal, "fake is failing as requested")
	}
	for i := range shifts {
		shifts[i].EvtID = strconv.Itoa(f.id)
		f.id++
	}
	return shifts, nil
}

func TestNew(t *testing.T) {

	tests := []struct {
		name string
		fail bool
		opts *Options
	}{{
		name: "Success",
		opts: &Options{
			URL:        "http://localhost:8080",
			ProdENV:    "production",
			Generators: &algo.Generators{},
			MemberStore: func(ctx context.Context) rotang.MemberStorer {
				return datastore.New(ctx)
			},
			ShiftStore: func(ctx context.Context) rotang.ShiftStorer {
				return datastore.New(ctx)
			},
			ConfigStore: func(ctx context.Context) rotang.ConfigStorer {
				return datastore.New(ctx)
			},
			Calendar: &calendar.Calendar{},
		},
	}, {
		name: "Options nil",
		fail: true,
	}, {
		name: "URL empty",
		fail: true,
		opts: &Options{
			Generators: &algo.Generators{},
			ProdENV:    "production",
			MemberStore: func(ctx context.Context) rotang.MemberStorer {
				return datastore.New(ctx)
			},
			ShiftStore: func(ctx context.Context) rotang.ShiftStorer {
				return datastore.New(ctx)
			},
			ConfigStore: func(ctx context.Context) rotang.ConfigStorer {
				return datastore.New(ctx)
			},
			Calendar: &calendar.Calendar{},
		},
	}, {
		name: "Generators Empty",
		fail: true,
		opts: &Options{
			URL:     "http://localhost:8080",
			ProdENV: "production",
			MemberStore: func(ctx context.Context) rotang.MemberStorer {
				return datastore.New(ctx)
			},
			ShiftStore: func(ctx context.Context) rotang.ShiftStorer {
				return datastore.New(ctx)
			},
			ConfigStore: func(ctx context.Context) rotang.ConfigStorer {
				return datastore.New(ctx)
			},
			Calendar: &calendar.Calendar{},
		},
	}, {
		name: "Store empty",
		fail: true,
		opts: &Options{
			URL:        "http://localhost:8080",
			ProdENV:    "production",
			Generators: &algo.Generators{},
			Calendar:   &calendar.Calendar{},
			ConfigStore: func(ctx context.Context) rotang.ConfigStorer {
				return datastore.New(ctx)
			},
		},
	}, {
		name: "No Calendar",
		fail: true,
		opts: &Options{
			URL:        "http://localhost:8080",
			ProdENV:    "production",
			Generators: &algo.Generators{},
			MemberStore: func(ctx context.Context) rotang.MemberStorer {
				return datastore.New(ctx)
			},
			ShiftStore: func(ctx context.Context) rotang.ShiftStorer {
				return datastore.New(ctx)
			},
			ConfigStore: func(ctx context.Context) rotang.ConfigStorer {
				return datastore.New(ctx)
			},
		},
	}, {
		name: "No ProdENV",
		fail: true,
		opts: &Options{
			URL:        "http://localhost:8080",
			Generators: &algo.Generators{},
			MemberStore: func(ctx context.Context) rotang.MemberStorer {
				return datastore.New(ctx)
			},
			ShiftStore: func(ctx context.Context) rotang.ShiftStorer {
				return datastore.New(ctx)
			},
			ConfigStore: func(ctx context.Context) rotang.ConfigStorer {
				return datastore.New(ctx)
			},
			Calendar: &calendar.Calendar{},
		},
	}}

	for _, tst := range tests {
		_, err := New(tst.opts)
		if got, want := (err != nil), tst.fail; got != want {
			t.Errorf("%s: New(_) = %t want: %t, err: %v", tst.name, got, want, err)
			continue
		}
	}
}
