// Copyright 2017 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package main

import (
	"sort"
	"sync"
	"time"

	log "github.com/luci/luci-go/common/logging"

	"golang.org/x/net/context"
)

type reportStep struct {
	name      string
	instances int
	delta     time.Duration
}

type reportBuilder struct {
	lock sync.Mutex

	tasks      map[string]*compareResult
	stepDeltas map[string]time.Duration
}

func (rb *reportBuilder) addTask(task string, cr *compareResult) {
	steps := cr.comparisonSteps()

	rb.lock.Lock()
	defer rb.lock.Unlock()
	if _, ok := rb.tasks[task]; ok {
		return
	}
	if rb.tasks == nil {
		rb.tasks = make(map[string]*compareResult)
	}
	rb.tasks[task] = cr

	// Ingest the steps.
	for _, step := range steps {
		if rb.stepDeltas == nil {
			rb.stepDeltas = make(map[string]time.Duration)
		}
		rb.stepDeltas[step.key] += step.delta()
	}
}

func (rb *reportBuilder) generateReport() *report {
	var r report

	var stepMap map[string]*reportStep
	for _, cr := range rb.tasks {
		steps := cr.comparisonSteps()
		if stepMap == nil {
			stepMap = make(map[string]*reportStep, len(steps))
		}

		for _, cs := range steps {
			rs := stepMap[cs.key]
			if rs == nil {
				rs = &reportStep{
					name: cs.name(),
				}
				stepMap[cs.key] = rs
			}

			rs.instances++
			rs.delta += cs.delta()
		}

		r.instances++
		r.delta += cr.delta()
	}

	r.steps = make([]*reportStep, 0, len(stepMap))
	for _, rs := range stepMap {
		r.steps = append(r.steps, rs)
	}
	sort.Slice(r.steps, func(i, j int) bool { return r.steps[i].delta < r.steps[j].delta })

	return &r
}

type report struct {
	delta     time.Duration
	instances int

	steps []*reportStep
}

func (r *report) log(c context.Context) {
	if r.delta > 0 {
		log.Warningf(c, "SwarmBucket took an average of %s longer (%s total).", average(r.delta, r.instances), r.delta)
	} else {
		log.Infof(c, "SwarmBucket took an average of %s shorter (%s total).", average(r.delta, r.instances), r.delta)
	}

	for _, rs := range r.steps {
		if rs.delta > 0 {
			log.Warningf(c, "Step %q adds %s on average in SwarmBucket (%s total).",
				rs.name, average(rs.delta, rs.instances), rs.delta)
		}
	}
}

func average(total time.Duration, count int) time.Duration {
	return time.Duration(float64(total) / float64(count))
}
