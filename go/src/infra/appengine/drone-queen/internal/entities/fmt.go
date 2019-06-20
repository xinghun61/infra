// Copyright 2019 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package entities

import (
	"bufio"
	"fmt"
	"io"
	"strings"
)

// FormatDUTs formats a slice of DUTs as a human readable string.
func FormatDUTs(d []*DUT) string {
	var b strings.Builder
	b.WriteString("[")
	if len(d) > 0 {
		writeDUT(&b, d[0])
		for _, d := range d[1:] {
			b.WriteString(", ")
			writeDUT(&b, d)
		}
	}
	b.WriteString("]")
	return b.String()
}

// writeDUT writes a human readable representation of the DUT.
func writeDUT(w io.Writer, d *DUT) error {
	bw := bufio.NewWriter(w)
	fmt.Fprintf(bw, "DUT %s (", d.ID)
	if dr := d.AssignedDrone; dr == "" {
		bw.WriteString("unassigned")
	} else {
		fmt.Fprintf(bw, "assigned to %s", dr)
	}
	if d.Draining {
		bw.WriteString(", draining")
	}
	bw.WriteString(")")
	return bw.Flush()
}
