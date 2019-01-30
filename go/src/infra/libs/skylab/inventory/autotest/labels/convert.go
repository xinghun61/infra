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

type converter func(*inventory.SchedulableLabels) []string
