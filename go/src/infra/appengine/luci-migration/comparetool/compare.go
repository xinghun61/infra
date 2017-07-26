// Copyright 2017 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package main

import (
	"sort"
	"strings"
	"time"

	"github.com/luci/luci-go/common/proto/google"
	miloProto "github.com/luci/luci-go/common/proto/milo"
)

type lineage map[*miloProto.Step]*miloProto.Step

func (l lineage) seen(st *miloProto.Step) bool {
	_, ok := l[st]
	return ok
}

func (l lineage) record(parent, st *miloProto.Step) {
	l[st] = parent
}

func (l lineage) trace(st *miloProto.Step) []*miloProto.Step {
	var steps []*miloProto.Step
	seen := make(map[*miloProto.Step]struct{})
	for st != nil {
		if _, ok := seen[st]; ok {
			panic("cyclical")
		}
		seen[st] = struct{}{}

		steps, st = append(steps, st), l[st]
	}

	for i := 0; i < len(steps)/2; i++ {
		pos := len(steps) - i - 1
		steps[i], steps[pos] = steps[pos], steps[i]
	}
	return steps
}

type comparisonStep struct {
	key string
	lhs *miloProto.Step
	rhs *miloProto.Step
}

func (cs *comparisonStep) name() string {
	return strings.Replace(cs.key, "\x00", "::", -1)
}

func (cs *comparisonStep) delta() time.Duration { return stepDuration(cs.rhs) - stepDuration(cs.lhs) }

type stepDebut struct {
	key   string
	debut time.Duration
}

type compareDelta struct {
	name  string
	delta time.Duration
}

type compareResult struct {
	lhs *miloProto.Step
	rhs *miloProto.Step

	lineage   lineage
	stepMap   map[string]*comparisonStep
	stepOrder []*stepDebut
}

func compare(lhs, rhs *miloProto.Step) *compareResult {
	cr := compareResult{
		lhs:     lhs,
		rhs:     rhs,
		lineage: make(lineage),
		stepMap: make(map[string]*comparisonStep),
	}

	cr.indexStep(lhs, lhs, func(cs *comparisonStep, st *miloProto.Step) { cs.lhs = st })
	cr.indexStep(rhs, rhs, func(cs *comparisonStep, st *miloProto.Step) { cs.rhs = st })

	// Ensure that "stepOrder" is in order of debut, first LHS then RHS.
	sort.Slice(cr.stepOrder, func(i, j int) bool { return cr.stepOrder[i].debut < cr.stepOrder[j].debut })

	return &cr
}

func (cr *compareResult) delta() time.Duration { return stepDuration(cr.rhs) - stepDuration(cr.lhs) }

func (cr *compareResult) comparisonSteps() []*comparisonStep {
	result := make([]*comparisonStep, len(cr.stepOrder))
	for i, sd := range cr.stepOrder {
		result[i] = cr.stepMap[sd.key]
	}
	return result
}

func (cr *compareResult) indexStep(base, st *miloProto.Step, csFunc func(*comparisonStep, *miloProto.Step)) {
	if base == st {
		// Initial parent index. Add to lineage.
		cr.lineage.record(nil, st)
	}

	stepKey := cr.makeStepKey(st)
	cs := cr.stepMap[stepKey]
	if cs == nil {
		offset := google.TimeFromProto(st.Started).Sub(google.TimeFromProto(base.Started))

		cs = &comparisonStep{
			key: stepKey,
		}
		cr.stepMap[stepKey] = cs
		cr.stepOrder = append(cr.stepOrder, &stepDebut{stepKey, offset})
	}
	csFunc(cs, st)

	for _, subStep := range st.Substep {
		if childStep := subStep.GetStep(); childStep != nil {
			cr.lineage.record(st, childStep)
			cr.indexStep(base, childStep, csFunc)
		}
	}
}

func (cr *compareResult) makeStepKey(st *miloProto.Step) string {
	steps := cr.lineage.trace(st)
	parts := make([]string, len(steps))
	for i, st := range steps {
		parts[i] = st.Name
	}
	return strings.Join(parts, "\x00")
}

func stepDuration(st *miloProto.Step) time.Duration {
	if st == nil {
		return 0
	}

	started := google.TimeFromProto(st.Started)
	ended := google.TimeFromProto(st.Ended)
	if started.IsZero() || ended.IsZero() {
		return 0
	}
	return ended.Sub(started)
}
