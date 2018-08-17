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

package priority

import (
	"fmt"
	"reflect"
	"testing"
	"time"

	"github.com/golang/protobuf/ptypes"
	"github.com/golang/protobuf/ptypes/timestamp"

	"infra/qscheduler/qslib/types"
	"infra/qscheduler/qslib/types/account"
	"infra/qscheduler/qslib/types/task"
	"infra/qscheduler/qslib/types/vector"
)

// epoch is an arbitrary time for testing purposes, corresponds to
// 01/01/2018 @ 1:00 am UTC
var epoch = time.Unix(1514768400, 0)

func TestBasicPrioritization(t *testing.T) {
	t.Parallel()

	cases := []struct {
		state    types.State
		config   types.Config
		expected OrderedRequests
	}{
		// One request with quota, should be given appropriate priority.
		{
			types.State{
				Balances: map[string]*vector.Vector{"a1": vector.New(1, 0, 0)},
				Requests: map[string]*task.Request{
					"t1": &task.Request{Id: "t1", AccountId: "a1"},
				},
			},
			*types.NewConfig(),
			[]Request{{Priority: 0, Request: &task.Request{Id: "t1", AccountId: "a1"}}},
		},

		// One request without quota, should be in the FreeBucket.
		{
			types.State{
				Requests: map[string]*task.Request{"t1": &task.Request{Id: "t1"}},
			},
			*types.NewConfig(),
			[]Request{{Priority: account.FreeBucket, Request: &task.Request{Id: "t1"}}},
		},
	}

	for _, test := range cases {
		actual := PrioritizeRequests(&test.state, &test.config)
		if !reflect.DeepEqual(actual, test.expected) {
			t.Errorf("With state %+v got priority slice %+v, want %+v", test.state, actual, test.expected)
		}
	}
}

// Given two requests with otherwise equal account-based priority,
// the earlier one should be given priority.
func TestPrioritizeWithEnqueueTimeTieBreaker(t *testing.T) {
	t.Parallel()
	e := time.Unix(100, 100)
	l := e.Add(10 * time.Second)

	eT := toStamp(e)
	lT := toStamp(l)

	eR := task.Request{AccountId: "a1", Id: "t1", EnqueueTime: eT}
	lR := task.Request{AccountId: "a1", Id: "t2", EnqueueTime: lT}

	state := types.State{
		Balances: map[string]*vector.Vector{"a1": vector.New(1, 0, 0)},
		Requests: map[string]*task.Request{
			"t2": &lR,
			"t1": &eR,
		},
	}
	actual := PrioritizeRequests(&state, types.NewConfig())
	expected := OrderedRequests([]Request{
		{Priority: 0, Request: &eR},
		{Priority: 0, Request: &lR},
	})
	if !reflect.DeepEqual(actual, expected) {
		t.Errorf("Got %+v, want %+v", actual, expected)
	}
}

// For a given account, once the number of running or requested tasks
// exceeds that account's MaxFanout, further requests should be assigned
// to the FreeBucket.
func TestDemoteBeyondFanout(t *testing.T) {
	t.Parallel()
	config := &types.Config{
		AccountConfigs: map[string]*account.Config{
			"a1": {MaxFanout: 3},
			"a2": {},
		},
	}
	running := []*task.Run{
		{Priority: 0, Request: &task.Request{AccountId: "a1", Id: "1"}},
		{Priority: 0, Request: &task.Request{AccountId: "a1", Id: "2"}},
		{Priority: 0, Request: &task.Request{AccountId: "a2", Id: "3"}},
		{Priority: account.FreeBucket, Request: &task.Request{AccountId: "a3", Id: "4"}},
	}
	workers := getWorkers(running)

	r1 := task.Request{AccountId: "a1", Id: "5"}
	r2 := task.Request{AccountId: "a1", Id: "6"}
	r3 := task.Request{AccountId: "a2", Id: "7"}
	r4 := task.Request{AccountId: "a3", Id: "8"}
	reqs := map[string]*task.Request{
		"5": &r1,
		"6": &r2,
		"7": &r3,
		"8": &r4,
	}
	state := &types.State{
		Balances: map[string]*vector.Vector{
			"a1": {},
			"a2": {},
		},
		Requests: reqs,
		Workers:  workers,
	}

	priList := []Request{
		{Priority: 0, Request: &r1},
		{Priority: 0, Request: &r2},
		{Priority: 0, Request: &r3},
		{Priority: account.FreeBucket, Request: &r4},
	}

	expected := []Request{
		{Priority: 0, Request: &r1},
		// This request got demoted from P0 to FreeBucket because it
		// exceeded the account's max fanout.
		{Priority: account.FreeBucket, Request: &r2},
		{Priority: 0, Request: &r3},
		{Priority: account.FreeBucket, Request: &r4},
	}

	demoteTasksBeyondFanout(priList, state, config)

	actual := priList
	if !reflect.DeepEqual(actual, expected) {
		t.Errorf("Got %+v, want %+v", actual, expected)
	}
}

// Run a thorough test of the full set of prioritization behaviors.
func TestPrioritize(t *testing.T) {
	t.Parallel()
	// Setup common variables.
	a1 := "a1"
	a2 := "a2"
	a3 := "a3"
	a4 := "a4"
	// a1: Account with P0 quota, fanout limit 3.
	// a2: Account with P1 quota, no fanout limit.
	// a3: Account with no quota.
	// a4: Invalid / nonexistent account.
	balances := map[string]*vector.Vector{
		a1: vector.New(1, 0, 0),
		a2: vector.New(0, 1, 0),
		a3: vector.New(),
	}
	config := &types.Config{
		AccountConfigs: map[string]*account.Config{
			a1: &account.Config{MaxFanout: 3},
			a2: &account.Config{},
			a3: &account.Config{},
		},
	}

	// 6 Jobs are already running. 2 for A1, 2 for A2, 1 for each of A3, A4
	run1 := task.Run{Priority: 0, Request: &task.Request{AccountId: a1}}
	run2 := task.Run{Priority: 0, Request: &task.Request{AccountId: a1}}
	run3 := task.Run{Priority: 1, Request: &task.Request{AccountId: a2}}
	run4 := task.Run{Priority: 1, Request: &task.Request{AccountId: a2}}
	run5 := task.Run{Priority: 3, Request: &task.Request{AccountId: a3}}
	run6 := task.Run{Priority: 3, Request: &task.Request{AccountId: a4}}
	running := []*task.Run{
		&run1,
		&run2,
		&run3,
		&run4,
		&run5,
		&run6,
	}

	// 6 Jobs are requested. 3 for A1, 1 for each of the remaining
	// A3's requests are the earliest, and 1 second apart.
	req1 := task.Request{AccountId: a1, EnqueueTime: atTime(0), Id: "1"}
	req2 := task.Request{AccountId: a1, EnqueueTime: atTime(1), Id: "2"}
	req3 := task.Request{AccountId: a1, EnqueueTime: atTime(2), Id: "3"}
	// The remaining requests are later by 1 second each.
	req4 := task.Request{AccountId: a2, EnqueueTime: atTime(3), Id: "4"}
	req5 := task.Request{AccountId: a3, EnqueueTime: atTime(4), Id: "5"}
	req6 := task.Request{AccountId: a4, EnqueueTime: atTime(5), Id: "6"}

	reqs := map[string]*task.Request{
		"1": &req1,
		"2": &req2,
		"3": &req3,
		"4": &req4,
		"5": &req5,
		"6": &req6,
	}

	state := &types.State{
		Balances: balances,
		Requests: reqs,
		Workers:  getWorkers(running),
	}

	expected := OrderedRequests([]Request{
		// A1 gets one additional request at P0, prior to overflowing fanout.
		{Priority: 0, Request: &req1},
		// A2 gets a P1 request.
		{Priority: 1, Request: &req4},
		// Remaining requests are all in the free bucket, ordered by enqueue time.
		{Priority: account.FreeBucket, Request: &req2},
		{Priority: account.FreeBucket, Request: &req3},
		{Priority: account.FreeBucket, Request: &req5},
		{Priority: account.FreeBucket, Request: &req6},
	})

	actual := PrioritizeRequests(state, config)

	if len(actual) != len(expected) {
		t.Errorf("len(actual) != len(expected)")
	}

	for i, exp := range expected {
		act := actual[i]
		if !reflect.DeepEqual(act, exp) {
			t.Errorf("%dth element of slices differ, got %+v, want %+v", i, act, exp)
		}
	}
}

func TestForPriority(t *testing.T) {
	t.Parallel()
	pRequests := OrderedRequests([]Request{
		Request{Priority: 0},
		Request{Priority: 0},
		Request{Priority: 1},
		Request{Priority: 3},
		Request{Priority: 3},
		Request{Priority: 4},
	})

	expecteds := []OrderedRequests{
		pRequests[0:2],
		pRequests[2:3],
		pRequests[3:3],
		pRequests[3:5],
		pRequests[5:6],
		pRequests[6:6],
	}

	for p := int32(0); p < 6; p++ {
		actual := pRequests.ForPriority(p)
		expected := expecteds[p]
		if !reflect.DeepEqual(actual, expected) {
			t.Errorf("P%d slice of: %+v \nwas %+v, \nwant %+v",
				p, pRequests, actual, expected)
		}
	}
}

// atTime is a helper method to create proto.Timestamp objects at various
// times relative to a fixed "0" time.
func atTime(seconds time.Duration) *timestamp.Timestamp {
	// Totally arbitrary but predictable "0" time.
	timeAfter := epoch.Add(seconds * time.Second)
	ans, _ := ptypes.TimestampProto(timeAfter)
	return ans
}

func toStamp(t time.Time) *timestamp.Timestamp {
	ts, err := ptypes.TimestampProto(t)
	if err != nil {
		panic(err)
	}
	return ts
}

// getWorkers is a helper function to turn a slice of running tasks
// into a workers map.
func getWorkers(running []*task.Run) map[string]*types.Worker {
	workers := make(map[string]*types.Worker)
	for i, r := range running {
		wid := fmt.Sprintf("w%d", i)
		workers[wid] = &types.Worker{Id: wid, Labels: []string{}, RunningTask: r}
	}
	return workers
}
