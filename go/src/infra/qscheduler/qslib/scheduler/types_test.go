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

// TODO(akeshet): The tests in this file make use of a lot of unexported
// methods and fields. It would be better if they were rewritten to use
// only the exported API of the scheduler. That would also entail building
// an exported API for getting job prioritization.

package scheduler

import (
	"context"
	"testing"
	"time"

	"github.com/kylelemons/godebug/pretty"
	. "github.com/smartystreets/goconvey/convey"

	"go.chromium.org/luci/common/data/stringset"
)

func TestClone(t *testing.T) {
	Convey("Given a state with some balances, accounts, and requests", t, func() {
		ctx := context.Background()
		tm := time.Unix(100, 0).UTC()
		s := New(tm)
		s.AddAccount(ctx, "aid", NewAccountConfig(1, 1, []float32{2, 3, 4}), nil)
		s.AddRequest(ctx, NewTaskRequest("req1", "a1", stringset.NewFromSlice("provision 1", "provision 2"), stringset.NewFromSlice("base 1", "base 2"), tm), tm, nil, NullEventSink)
		s.AddRequest(ctx, NewTaskRequest("req2", "a1", stringset.NewFromSlice("provision 3", "provision 4"), stringset.NewFromSlice("base 3", "base 4"), tm), tm, nil, NullEventSink)
		s.MarkIdle(ctx, "worker 1", stringset.NewFromSlice("base 1", "base 2"), tm, NullEventSink)
		s.MarkIdle(ctx, "worker 2", stringset.NewFromSlice("base foo", "base bar"), tm, NullEventSink)
		s.RunOnce(ctx, NullEventSink)
		Convey("when state is Cloned via proto roundtrip, it should resemble itself.", func() {
			sClone := s.state.Clone()
			diff := pretty.Compare(s.state, sClone)
			So(diff, ShouldBeBlank)
		})
	})
}
