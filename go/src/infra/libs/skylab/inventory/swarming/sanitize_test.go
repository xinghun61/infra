// Copyright 2019 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package swarming

import (
	"reflect"
	"testing"
)

type fakeReporter []error

func (r *fakeReporter) Report(err error) {
	*r = append(*r, err)
}

func TestSanitize(t *testing.T) {
	t.Parallel()
	const longKey = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
	const longVal = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
	cases := []struct {
		name  string
		input Dimensions
		want  Dimensions
		errs  []error
	}{
		{
			name:  "empty key",
			input: Dimensions{"": {}, "uss": {"essex"}},
			want:  Dimensions{"uss": {"essex"}},
			errs:  []error{ErrEmptyKey},
		},
		{
			name:  "long key",
			input: Dimensions{longKey: {}, "uss": {"essex"}},
			want:  Dimensions{"uss": {"essex"}},
			errs:  []error{ErrLongKey{Key: longKey}},
		},
		{
			name:  "invalid key chars",
			input: Dimensions{"!!": {}, "uss": {"essex"}},
			want:  Dimensions{"uss": {"essex"}},
			errs:  []error{ErrKeyChars{Key: "!!"}},
		},
		{
			name:  "empty value",
			input: Dimensions{"uss": {"essex", ""}},
			want:  Dimensions{"uss": {"essex"}},
			errs:  []error{ErrEmptyValue{Key: "uss"}},
		},
		{
			name:  "long value",
			input: Dimensions{"uss": {"essex", longVal}},
			want:  Dimensions{"uss": {"essex"}},
			errs:  []error{ErrLongValue{Key: "uss", Value: longVal}},
		},
		{
			name:  "dupe value",
			input: Dimensions{"uss": {"essex", "yorktown", "essex"}},
			want:  Dimensions{"uss": {"essex", "yorktown"}},
			errs:  []error{ErrRepeatedValue{Key: "uss", Value: "essex"}},
		},
		{
			name:  "key with digit as first character",
			input: Dimensions{"123key": {"essex"}},
			want:  Dimensions{},
			errs:  []error{ErrKeyChars{Key: "123key"}},
		},
		{
			name:  "key with digit after first character",
			input: Dimensions{"key123": {"essex"}},
			want:  Dimensions{"key123": {"essex"}},
		},
	}
	for _, c := range cases {
		c := c
		t.Run(c.name, func(t *testing.T) {
			t.Parallel()
			dims := copyDims(c.input)
			var r fakeReporter
			Sanitize(dims, r.Report)
			if !reflect.DeepEqual(dims, c.want) {
				t.Errorf("Sanitize(%#v, r) = %#v; want %#v", c.input, dims, c.want)
			}
			if !reflect.DeepEqual([]error(r), c.errs) {
				t.Errorf("Got errors %#v; want %#v", []error(r), c.errs)
			}
		})
	}
}

func copyDims(dims Dimensions) Dimensions {
	new := make(Dimensions, len(dims))
	for k, v := range dims {
		new[k] = make([]string, len(v))
		copy(new[k], v)
	}
	return new
}

func TestDeleteValue(t *testing.T) {
	t.Parallel()
	cases := []struct {
		name  string
		input []string
		i     int
		want  []string
	}{
		{name: "middle", input: []string{"1", "2", "3"}, i: 1, want: []string{"1", "3"}},
		{name: "start", input: []string{"1", "2", "3"}, i: 0, want: []string{"2", "3"}},
		{name: "end", input: []string{"1", "2", "3"}, i: 2, want: []string{"1", "2"}},
	}
	for _, c := range cases {
		c := c
		t.Run(c.name, func(t *testing.T) {
			t.Parallel()
			s := make([]string, len(c.input))
			copy(s, c.input)
			s = deleteValue(s, c.i)
			if !reflect.DeepEqual(s, c.want) {
				t.Errorf("deleteValue(%#v, %#v) = %#v; want %#v", c.input, c.i, s, c.want)
			}
		})
	}
}

func TestIsDupe(t *testing.T) {
	t.Parallel()
	cases := []struct {
		name  string
		input []string
		i     int
		want  bool
	}{
		{name: "true", input: []string{"1", "2", "2"}, i: 2, want: true},
		{name: "false", input: []string{"1", "2", "3"}, i: 2, want: false},
		{name: "start", input: []string{"2", "2", "2"}, i: 0, want: false},
	}
	for _, c := range cases {
		c := c
		t.Run(c.name, func(t *testing.T) {
			t.Parallel()
			got := isDupe(c.input, c.i)
			if got != c.want {
				t.Errorf("isDupe(%#v, %#v) = %#v; want %#v", c.input, c.i, got, c.want)
			}
		})
	}
}

func BenchmarkIsDupe(b *testing.B) {
	s := []string{"1", "2", "3", "4", "5", "6", "7", "8", "9", "10"}
	for i := 0; i < b.N; i++ {
		for j := 0; j < len(s); j++ {
			isDupe(s, j)
		}
	}
}

func BenchmarkIsDupeMap(b *testing.B) {
	s := []string{"1", "2", "3", "4", "5", "6", "7", "8", "9", "10"}
	for i := 0; i < b.N; i++ {
		seen := make(map[string]bool, len(s))
		for j := 0; j < len(s); j++ {
			v := s[j]
			if seen[v] {
				continue
			}
			seen[v] = true
		}
	}
}
