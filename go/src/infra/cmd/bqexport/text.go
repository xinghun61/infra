// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"strings"
	"unicode"
)

func toCamelCase(v string) string {
	needsUpper := true
	result := make([]rune, 0, len(v))
	for _, r := range v {
		if unicode.IsLetter(r) || unicode.IsNumber(r) {
			if needsUpper {
				r = unicode.ToUpper(r)
				needsUpper = false
			}
			result = append(result, r)
		} else {
			needsUpper = true
		}
	}
	return string(result)
}

// camelCaseToUnderscore converts a camel-case string to a lowercase string
// with underscore delimiters.
func camelCaseToUnderscore(v string) string {
	var parts []string
	var segment []rune
	addSegment := func() {
		if len(segment) > 0 {
			parts = append(parts, string(segment))
			segment = segment[:0]
		}
	}

	for _, r := range v {
		switch {
		case unicode.IsUpper(r):
			r = unicode.ToLower(r)
			addSegment()
		case unicode.IsLetter(r), unicode.IsNumber(r):
		default:
			r = '_'
		}
		segment = append(segment, r)
	}
	addSegment()
	return strings.Join(parts, "_")
}
