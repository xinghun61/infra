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

package clients

import (
	"testing"
	"time"

	"github.com/golang/protobuf/ptypes/duration"
	swarming "go.chromium.org/luci/common/api/swarming/swarming/v1"

	fleet "infra/appengine/crosskylabadmin/api/fleet/v1"
)

func TestGetStateDimension(t *testing.T) {
	t.Parallel()
	cases := []struct {
		name  string
		input []*swarming.SwarmingRpcsStringListPair
		want  fleet.DutState
	}{
		{"missing key", nil, fleet.DutState_DutStateInvalid},
		{"normal", []*swarming.SwarmingRpcsStringListPair{
			{Key: "dut_state", Value: []string{"ready"}},
		}, fleet.DutState_Ready},
		{"multiple values", []*swarming.SwarmingRpcsStringListPair{
			{Key: "dut_state", Value: []string{"ready", "repair_failed"}},
		}, fleet.DutState_DutStateInvalid},
		{"multiple pairs", []*swarming.SwarmingRpcsStringListPair{
			{Key: "dut_state", Value: []string{"ready"}},
			{Key: "dut_state", Value: []string{"repair_failed"}},
		}, fleet.DutState_Ready},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			t.Parallel()
			got := GetStateDimension(c.input)
			if got != c.want {
				t.Errorf("getStateDimension(%#v) = %#v; want %#v", c.input, got, c.want)
			}
		})
	}
}

func TestTimeSinceBotTaskN(t *testing.T) {
	t.Parallel()
	now := time.Date(2016, 1, 2, 3, 4, 5, 0, time.UTC)
	assert := func(t *testing.T, got, want *duration.Duration) {
		t.Helper()
		switch want {
		case nil:
			if got != nil {
				t.Errorf("Got %#v instead of nil", got)
			}
		default:
			if got == nil {
				t.Errorf("Got nil instead of %#v", want)
				return
			}
			if got.Seconds != want.Seconds || got.Nanos != want.Nanos {
				t.Errorf("Got %#v instead of %#v", got, want)
			}
		}
	}
	cases := []struct {
		desc  string
		now   time.Time
		input swarming.SwarmingRpcsTaskResult
		want  *duration.Duration
	}{
		{
			desc: "completed",
			input: swarming.SwarmingRpcsTaskResult{
				State:       "COMPLETED",
				CompletedTs: "2016-01-02T03:04:01.000000009",
			},
			want: &duration.Duration{Seconds: 3, Nanos: 999999991},
		},
		{
			desc: "running",
			input: swarming.SwarmingRpcsTaskResult{
				State: "RUNNING",
			},
			want: &duration.Duration{Seconds: 0, Nanos: 0},
		},
		{
			desc: "killed",
			input: swarming.SwarmingRpcsTaskResult{
				State:       "KILLED",
				AbandonedTs: "2016-01-02T03:04:01.000000009",
			},
			want: &duration.Duration{Seconds: 3, Nanos: 999999991},
		},
		{
			desc: "expired",
			input: swarming.SwarmingRpcsTaskResult{
				State: "EXPIRED",
			},
			want: nil,
		},
	}
	for _, c := range cases {
		c := c
		t.Run(c.desc, func(t *testing.T) {
			t.Parallel()
			got, err := TimeSinceBotTaskN(&c.input, now)
			if err != nil {
				t.Fatalf("TimeSinceBotTaskN returned unexpected error: %s", err)
			}
			assert(t, got, c.want)
		})
	}
}

func TestTaskDoneTime(t *testing.T) {
	t.Parallel()
	cases := []struct {
		desc  string
		input swarming.SwarmingRpcsTaskResult
		want  time.Time
	}{
		{
			desc: "completed",
			input: swarming.SwarmingRpcsTaskResult{
				State:       "COMPLETED",
				CompletedTs: "2016-01-02T10:04:05.999999999",
			},
			want: time.Date(2016, 1, 2, 10, 4, 5, 999999999, time.UTC),
		},
		{
			desc: "timed out",
			input: swarming.SwarmingRpcsTaskResult{
				State:       "TIMED_OUT",
				CompletedTs: "2016-01-02T10:04:05.999999999",
			},
			want: time.Date(2016, 1, 2, 10, 4, 5, 999999999, time.UTC),
		},
		{
			desc: "running",
			input: swarming.SwarmingRpcsTaskResult{
				State: "RUNNING",
			},
			want: time.Time{},
		},
		{
			desc: "killed",
			input: swarming.SwarmingRpcsTaskResult{
				State:       "KILLED",
				AbandonedTs: "2016-01-02T10:04:05.999999999",
			},
			want: time.Date(2016, 1, 2, 10, 4, 5, 999999999, time.UTC),
		},
		{
			desc: "expired",
			input: swarming.SwarmingRpcsTaskResult{
				State: "EXPIRED",
			},
			want: time.Time{},
		},
	}
	for _, c := range cases {
		c := c
		t.Run(c.desc, func(t *testing.T) {
			t.Parallel()
			got, err := TaskDoneTime(&c.input)
			if err != nil {
				t.Fatalf("TaskDoneTime returned unexpected error: %s", err)
			}
			if !got.Equal(c.want) {
				t.Errorf("TaskDoneTime(%#v) = %s; want %s", c.input, got.Format(time.RFC3339Nano),
					c.want.Format(time.RFC3339Nano))
			}
		})
	}
}
