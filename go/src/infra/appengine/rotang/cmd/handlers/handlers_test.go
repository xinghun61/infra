// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package handlers

import (
	"infra/appengine/rotang"
	"infra/appengine/rotang/pkg/algo"
	"infra/appengine/rotang/pkg/datastore"
	"testing"

	"golang.org/x/net/context"
)

func TestNew(t *testing.T) {

	tests := []struct {
		name string
		fail bool
		opts *Options
	}{{
		name: "Success",
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
		},
	}, {
		name: "Options nil",
		fail: true,
	}, {
		name: "URL empty",
		fail: true,
		opts: &Options{
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
		name: "Generators Empty",
		fail: true,
		opts: &Options{
			URL: "http://localhost:8080",
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
		name: "Store empty",
		fail: true,
		opts: &Options{
			URL:        "http://localhost:8080",
			Generators: &algo.Generators{},
			ConfigStore: func(ctx context.Context) rotang.ConfigStorer {
				return datastore.New(ctx)
			},
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
