// Copyright 2018 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package flagx

import (
	"flag"
	"io/ioutil"
	"reflect"
	"testing"
)

// Check that a JSON object string gets parsed correctly using JSONMap.
func TestParseJSONMap(t *testing.T) {
	t.Parallel()
	cases := []struct {
		arg      string
		expected map[string]string
	}{
		{`{"foo": "bar"}`, map[string]string{"foo": "bar"}},
	}
	for _, c := range cases {
		var m map[string]string
		fs := testFlagSet()
		fs.Var(JSONMap(&m), "map", "Some map")
		if err := fs.Parse([]string{"-map", c.arg}); err != nil {
			t.Errorf("Parse returned an error for %s: %s", c.arg, err)
			continue
		}
		if !reflect.DeepEqual(m, c.expected) {
			t.Errorf("Parsing %s, got %#v, expected %#v", c.arg, m, c.expected)
		}
	}
}

func testFlagSet() *flag.FlagSet {
	fs := flag.NewFlagSet("test", flag.ContinueOnError)
	fs.Usage = func() {}
	fs.SetOutput(ioutil.Discard)
	return fs
}
