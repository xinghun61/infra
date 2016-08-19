// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package model

var (
	// FailureLongNames is a map from short failure name to long failure
	// name.
	FailureLongNames = map[string]string{
		"A": "AUDIO",
		"C": "CRASH",
		"Q": "FAIL",
		"L": "FLAKY",
		"I": "IMAGE",
		"Z": "IMAGE+TEXT",
		"K": "LEAK",
		"O": "MISSING",
		"N": "NO DATA",
		"Y": "NOTRUN",
		"P": "PASS",
		"X": "SKIP",
		"S": "SLOW",
		"F": "TEXT",
		"T": "TIMEOUT",
		"U": "UNKNOWN",
		"V": "VERYFLAKY",
	}
	// FailureShortNames is a map from long failure name to short
	// failure name.
	FailureShortNames map[string]string
)

func init() {
	FailureShortNames = make(map[string]string)
	for k, v := range FailureLongNames {
		FailureShortNames[v] = k
	}
}
