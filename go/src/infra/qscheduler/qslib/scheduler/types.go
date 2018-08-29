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

package scheduler

import (
	"github.com/golang/protobuf/proto"

	"infra/qscheduler/qslib/types/account"
	"infra/qscheduler/qslib/types/task"
	"infra/qscheduler/qslib/types/vector"
)

// NewConfig creates an returns a new Config instance with all maps initialized.
func NewConfig() *Config {
	return &Config{
		AccountConfigs: map[string]*account.Config{},
	}
}

// NewState creates an returns a new State instance with all maps initialized.
func NewState() *State {
	return &State{
		Balances: map[string]*vector.Vector{},
		Requests: map[string]*task.Request{},
		Workers:  map[string]*Worker{},
	}
}

// Clone returns a deep copy of the given state.
func (s *State) Clone() *State {
	// Merge clone into intiated state, to ensure that any empty maps are preserved
	// as empty maps rather than turned into nil maps as proto.Clone would do
	// on its own.
	ns := NewState()
	proto.Merge(ns, proto.Clone(s))
	return ns
}
