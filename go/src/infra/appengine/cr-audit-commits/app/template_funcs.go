// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package crauditcommits implements cr-audit-commits.appspot.com services.
package crauditcommits

import (
	"fmt"
	"html/template"
	"strings"
	"time"
)

var (
	templateFuncs = template.FuncMap{
		// Format a time in the past in an easy-to-read low precision
		// string.
		"timeAgo": func(when time.Time) string {
			d := time.Since(when)
			switch {
			case d.Hours() >= 48.0:
				return fmt.Sprintf("%.f days ago", d.Hours()/24.0)
			case d.Hours() >= 2.0:
				return fmt.Sprintf("%.f hours ago", d.Hours())
			case d.Minutes() >= 2.0:
				return fmt.Sprintf("%.f minutes ago", d.Minutes())
			default:
				return fmt.Sprintf("%.f seconds ago", d.Seconds())
			}

		},
		// Return first line of commit message, abbrev. if needed.
		"commitSubject": func(msg string) string {
			firstLine := strings.SplitN(msg, "\n", 2)[0]
			if len(firstLine) <= 50 {
				return firstLine
			}
			return fmt.Sprintf("%.47s...", firstLine)
		},
	}
)
