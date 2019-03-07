// Copyright 2019 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package swarming implements conversion of Skylab inventory schema to
// Swarming dimensions.
package swarming

import "infra/libs/skylab/inventory"

// Dimensions is the type for Swarming dimensions.
type Dimensions map[string][]string

// Convert converts DUT inventory labels to Swarming dimensions.
func Convert(ls *inventory.SchedulableLabels) Dimensions {
	dims := make(Dimensions)
	for _, c := range converters {
		c(dims, ls)
	}
	return dims
}

var converters []converter

// converter is the type of functions used for converting Skylab
// inventory labels to Swarming dimensions.
type converter func(Dimensions, *inventory.SchedulableLabels)

// appendDim appends a dimension value for a key.
func appendDim(dim Dimensions, k, v string) {
	dim[k] = append(dim[k], v)
}
