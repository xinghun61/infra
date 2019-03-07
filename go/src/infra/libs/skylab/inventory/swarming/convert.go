// Copyright 2019 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package swarming implements conversion of Skylab inventory schema to
// Swarming dimensions.
package swarming

import "infra/libs/skylab/inventory"

// Convert converts DUT inventory labels to Swarming dimensions.
func Convert(ls *inventory.SchedulableLabels) map[string][]string {
	dims := make(map[string][]string)
	for _, c := range converters {
		c(dims, ls)
	}
	return dims
}

var converters []converter

// converter is the type of functions used for converting Skylab
// inventory labels to Swarming dimensions.
type converter func(map[string][]string, *inventory.SchedulableLabels)

// appendDim appends a dimension value for a key.
func appendDim(dim map[string][]string, k, v string) {
	dim[k] = append(dim[k], v)
}
