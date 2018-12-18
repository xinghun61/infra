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
	"time"

	"github.com/golang/protobuf/proto"

	"infra/qscheduler/qslib/tutils"
	"infra/qscheduler/qslib/types/account"
	"infra/qscheduler/qslib/types/vector"
)

// NewConfig creates an returns a new Config instance with all maps initialized.
func NewConfig() *Config {
	return &Config{
		AccountConfigs: map[string]*account.Config{},
	}
}

// NewState creates an returns a new State instance with all maps initialized.
func NewState(t time.Time) *StateProto {
	return &StateProto{
		Balances:       map[string]*vector.Vector{},
		QueuedRequests: map[string]*TaskRequest{},
		Workers:        map[string]*Worker{},
		LastUpdateTime: tutils.TimestampProto(t),
	}
}

// Clone returns a deep copy of the given state.
func (s *StateProto) Clone() *StateProto {
	// Merge clone into intiated state, to ensure that any empty maps are preserved
	// as empty maps rather than turned into nil maps as proto.Clone would do
	// on its own.
	ns := NewState(time.Unix(0, 0))
	// Time is a required argument to the above constructor, but we don't want to
	// specify it in the empty initialized state. This will get overwritten by
	// the merge below (unless it was missing from s).
	ns.LastUpdateTime = nil
	proto.Merge(ns, proto.Clone(s))
	return ns
}
