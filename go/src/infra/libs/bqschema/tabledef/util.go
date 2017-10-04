// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package tabledef

import (
	"fmt"
)

// ID returns the actual dataset ID string for a given data set enum.
func (ds TableDef_DataSet) ID() string {
	switch ds {
	case TableDef_RAW_EVENTS:
		return "raw_events"
	case TableDef_AGGREGATED:
		return "aggregated"
	case TableDef_TEST_DATA:
		return "test_data"
	default:
		panic(fmt.Errorf("unknown data set: %v", ds))
	}
}
