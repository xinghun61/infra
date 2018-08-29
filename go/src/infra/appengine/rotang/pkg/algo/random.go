// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package algo

import (
	"infra/appengine/rotang"
	"time"
)

// RandomGen implement a rota Generator scheduling random members to shifts.
type RandomGen struct {
}

var _ rotang.RotaGenerator = &RandomGen{}

// NewRandomGen returns an instance of the RandomGen generator.
func NewRandomGen() *RandomGen {
	return &RandomGen{}
}

// Generate generates shifts usings members at random.
func (r *RandomGen) Generate(sc *rotang.Configuration, start time.Time, previous []rotang.ShiftEntry, members []rotang.Member, shiftsToSchedule int) ([]rotang.ShiftEntry, error) {
	Random(members)
	if len(previous) > 0 {
		start = previous[len(previous)-1].EndTime
	}
	return MakeShifts(sc, start, members, shiftsToSchedule), nil
}

// Name returns the name of this Generator.
func (r *RandomGen) Name() string {
	return "Random"
}
