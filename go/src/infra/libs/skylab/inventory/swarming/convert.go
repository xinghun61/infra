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

// Revert converts Swarming dimensions to DUT inventory labels.
func Revert(d Dimensions) *inventory.SchedulableLabels {
	ls := inventory.NewSchedulableLabels()
	for _, r := range reverters {
		d = r(ls, d)
	}
	return ls
}

var reverters []reverter

// reverter is the type of functions used for reverting Swarming
// dimensions back to Skylab inventory labels.  Each reverter should
// modify the SchedulableLabels for the Swarming dimension it is
// responsible for, and return the Dimensions that it does not handle.
type reverter func(*inventory.SchedulableLabels, Dimensions) Dimensions

// appendDim appends a dimension value for a key.
func appendDim(dim Dimensions, k, v string) {
	dim[k] = append(dim[k], v)
}
