// Copyright 2018 The LUCI Authors.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//      http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

package simulation

import (
	"reflect"
	"testing"
	"time"

	"infra/qscheduler/qslib/tutils"
	"infra/qscheduler/qslib/types/task"
)

// Test the workload generator produces the expected output.
func TestGenerator(t *testing.T) {
	gens := make([]GeneratedTask, 0)

	ti := time.Unix(0, 0)
	w := &Workload{
		AccountId:         "a1",
		CyclesPerLabelSet: 2,
		Duration:          tutils.DurationProto(time.Minute),
		Num:               2,
		Period:            tutils.DurationProto(2 * time.Minute),
		Tag:               "w1",
	}
	g := NewGenerator(ti, w)

	nSeconds := 7 * 60

	for i := 0; i < nSeconds; i++ {
		ti = ti.Add(time.Second)
		gen := g.advanceTo(ti, w)
		gens = append(gens, gen...)
	}

	expects := []GeneratedTask{
		// Cycle 1
		{
			&task.Request{
				AccountId:   "a1",
				EnqueueTime: tutils.TimestampProto(time.Unix(120, 0)),
				Labels:      []string{"image_w1_0"},
			},
			time.Minute,
			"req_w1_0",
		},
		{
			&task.Request{
				AccountId:   "a1",
				EnqueueTime: tutils.TimestampProto(time.Unix(120, 0)),
				Labels:      []string{"image_w1_0"},
			},
			time.Minute,
			"req_w1_1",
		},
		// Cycle 2
		{
			&task.Request{
				AccountId:   "a1",
				EnqueueTime: tutils.TimestampProto(time.Unix(240, 0)),
				Labels:      []string{"image_w1_0"},
			},
			time.Minute,
			"req_w1_2",
		},
		{
			&task.Request{
				AccountId:   "a1",
				EnqueueTime: tutils.TimestampProto(time.Unix(240, 0)),
				Labels:      []string{"image_w1_0"},
			},
			time.Minute,
			"req_w1_3",
		},
		// Cycle 3 (new image)
		{
			&task.Request{
				AccountId:   "a1",
				EnqueueTime: tutils.TimestampProto(time.Unix(360, 0)),
				Labels:      []string{"image_w1_1"},
			},
			time.Minute,
			"req_w1_4",
		},
		{
			&task.Request{
				AccountId:   "a1",
				EnqueueTime: tutils.TimestampProto(time.Unix(360, 0)),
				Labels:      []string{"image_w1_1"},
			},
			time.Minute,
			"req_w1_5",
		},
	}

	if len(expects) != len(gens) {
		t.Errorf("Got %d reqs, want %d", len(gens), len(expects))
	}

	for i, e := range expects {
		if !(reflect.DeepEqual(e, gens[i])) {
			t.Errorf("Got %dth generated task %+v, want %+v", i, gens[i], e)
		}
	}
}
