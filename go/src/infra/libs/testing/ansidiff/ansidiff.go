// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package ansidiff

import (
	"bytes"
	"fmt"
	"github.com/mgutz/ansi"
	dmp "github.com/sergi/go-diff/diffmatchpatch"
)

// Diff returns a diff string indiciating edits with ANSI color encodings
// (red for deletions, green for additions).
func Diff(a, b interface{}) string {
	d := dmp.New()
	diffs := d.DiffMain(fmt.Sprintf("%+v", a), fmt.Sprintf("%+v", b), true)

	var buff bytes.Buffer
	for _, d := range diffs {
		switch d.Type {
		case dmp.DiffDelete:
			buff.WriteString(ansi.Color(d.Text, "red"))
		case dmp.DiffInsert:
			buff.WriteString(ansi.Color(d.Text, "green"))
		case dmp.DiffEqual:
			buff.WriteString(d.Text)
		}
	}
	return buff.String()
}
