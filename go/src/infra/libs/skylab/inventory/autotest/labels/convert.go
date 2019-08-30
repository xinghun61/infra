// Copyright 2019 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package labels implements conversion of Skylab inventory schema to
// Autotest labels.
package labels

import "infra/libs/skylab/inventory"

// Convert converts DUT inventory labels to Autotest labels.
func Convert(ls *inventory.SchedulableLabels) []string {
	var labels []string
	for _, c := range converters {
		labels = append(labels, c(ls)...)
	}
	return labels
}

var converters []converter

// converter is the type of functions used for converting Skylab
// inventory labels to Autotest labels.  Each converter should return
// the Autotest labels it is responsible for.
type converter func(*inventory.SchedulableLabels) []string

// Revert converts Autotest labels to DUT inventory labels.
func Revert(labels []string) *inventory.SchedulableLabels {
	ls := inventory.NewSchedulableLabels()
	for _, r := range reverters {
		labels = r(ls, labels)
	}
	return ls
}

var reverters []reverter

// reverter is the type of functions used for reverting Autotest
// labels back to Skylab inventory labels.  Each reverter should
// modify the SchedulableLabels for the Autotest labels it is
// responsible for, and return a slice of Autotest labels that it does
// not handle.
type reverter func(*inventory.SchedulableLabels, []string) []string
