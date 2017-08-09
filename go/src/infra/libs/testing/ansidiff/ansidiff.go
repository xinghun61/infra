// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package ansidiff

import (
	"bytes"
	"fmt"
	"os"
	"sync"

	dmp "github.com/sergi/go-diff/diffmatchpatch"
	"go.chromium.org/luci/common/system/terminal"
)

// Diff returns a diff string indiciating edits with ANSI color encodings
// (red for deletions, green for additions).
//
// Disables coloring if stdout of the current process is not connected to
// a terminal.
func Diff(a, b interface{}) string {
	d := dmp.New()
	diffs := d.DiffMain(fmt.Sprintf("%+v", a), fmt.Sprintf("%+v", b), true)

	var buff bytes.Buffer
	for _, d := range diffs {
		switch d.Type {
		case dmp.DiffDelete:
			buff.WriteString(red(d.Text))
		case dmp.DiffInsert:
			buff.WriteString(green(d.Text))
		case dmp.DiffEqual:
			buff.WriteString(d.Text)
		}
	}
	return buff.String()
}

var isTerm struct {
	sync.Once
	yep bool
}

func isTerminal() bool {
	isTerm.Do(func() {
		isTerm.yep = terminal.IsTerminal(int(os.Stdout.Fd()))
	})
	return isTerm.yep
}

func colored(text, esc string) string {
	if isTerminal() {
		return esc + text + "\033[00m"
	}
	return text
}

func red(text string) string {
	return colored(text, "\033[91m")
}

func green(text string) string {
	return colored(text, "\033[92m")
}
