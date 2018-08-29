// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package algo

import (
	"infra/appengine/rotang"
	"sort"
	"strings"
	"testing"
	"time"

	"github.com/kylelemons/godebug/pretty"
)

type testGenerator struct {
	name string
}

func (t *testGenerator) Name() string {
	return t.name
}

func (t *testGenerator) Generate(_ *rotang.Configuration, _ time.Time, _ []rotang.ShiftEntry, _ []rotang.Member, _ int) ([]rotang.ShiftEntry, error) {
	return nil, nil
}

var _ rotang.RotaGenerator = &testGenerator{}

func stringToGenerators(in string) []rotang.RotaGenerator {
	var res []rotang.RotaGenerator
	for _, c := range in {
		res = append(res, &testGenerator{
			name: string(c),
		})
	}
	return res
}

func TestRegisterList(t *testing.T) {

	tests := []struct {
		name       string
		generators string
		want       string
	}{
		{
			name:       "Single gen",
			generators: "A",
			want:       "A",
		}, {
			name:       "A few generators",
			generators: "ABCDEF",
			want:       "ABCDEF",
		}, {
			name:       "Duplicate generator",
			generators: "ABBA",
			want:       "AB",
		},
	}

	for _, tst := range tests {
		a := New()
		for _, g := range stringToGenerators(tst.generators) {
			a.Register(g)
		}
		got := []byte(strings.Join(a.List(), ""))
		want := []byte(tst.want)
		sort.Slice(got, func(i, j int) bool {
			return got[i] < got[j]
		})
		sort.Slice(want, func(i, j int) bool {
			return want[i] < want[j]
		})

		if diff := pretty.Compare(want, got); diff != "" {
			t.Errorf("%s: a.List() differs -want +got:\n %s", tst.name, diff)
		}
	}
}

func TestFetch(t *testing.T) {
	tests := []struct {
		name       string
		fail       bool
		generators string
		fetch      string
	}{
		{
			name:       "Success fetch",
			generators: "A",
			fetch:      "A",
		}, {
			name:       "Generator not exists",
			fail:       true,
			generators: "ACD",
			fetch:      "B",
		}, {
			name:       "Multiple generators",
			generators: "ABCDEFGHI",
			fetch:      "E",
		},
	}

	for _, tst := range tests {
		a := New()
		for _, g := range stringToGenerators(tst.generators) {
			a.Register(g)
		}
		_, err := a.Fetch(tst.fetch)
		if got, want := (err != nil), tst.fail; got != want {
			t.Errorf("%s: a.Fetch(%q) = %t want: %t, err: %v", tst.name, tst.fetch, got, want, err)
		}
	}
}
