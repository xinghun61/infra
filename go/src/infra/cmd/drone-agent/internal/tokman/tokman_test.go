// Copyright 2019 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package tokman

import (
	"io/ioutil"
	"os"
	"path/filepath"
	"testing"
	"time"

	"github.com/google/go-cmp/cmp"
	"golang.org/x/oauth2"
)

func TestWriteToken(t *testing.T) {
	t.Parallel()
	d, err := ioutil.TempDir("", "test")
	if err != nil {
		t.Fatal(err)
	}
	defer os.RemoveAll(d)
	f := filepath.Join(d, "key.json")
	if err := ioutil.WriteFile(f, []byte("blah"), 0600); err != nil {
		t.Fatal(err)
	}
	tok := &oauth2.Token{
		AccessToken: "ya29.Gl1uB45Ecullaaaaaaaaa",
		Expiry:      time.Date(2001, 2, 3, 4, 5, 6, 7, time.UTC),
	}
	if err := writeToken(tok, f); err != nil {
		t.Fatal(err)
	}
	got, err := ioutil.ReadFile(f)
	if err != nil {
		t.Fatal(err)
	}
	want := `{"token":"ya29.Gl1uB45Ecullaaaaaaaaa","expiry":981173106}
`
	if diff := cmp.Diff(want, string(got)); diff != "" {
		t.Errorf("token mismatch (-want +got):\n%s", diff)
	}
}

func TestRandRange(t *testing.T) {
	t.Parallel()
	cases := []struct {
		desc string
		v    float32
		x    float32
		want float32
	}{
		{".5", .5, 2, 0},
		{".75", .75, 2, 1},
		{".25", .25, 2, -1},
		{"0", 0, 2, -2},
	}
	for _, c := range cases {
		c := c
		t.Run(c.desc, func(t *testing.T) {
			t.Parallel()
			got := randRange(stubRander{c.v}, c.x)
			if got != c.want {
				t.Errorf("randRange(%v, %v) = %v; want %v", c.v, c.x, got, c.want)
			}
		})
	}
}

type stubRander struct {
	v float32
}

func (s stubRander) Float32() float32 {
	return s.v
}
