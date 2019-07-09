// Copyright 2019 The LUCI Authors.
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

package profiler

import (
	"fmt"
	"testing"

	"github.com/golang/protobuf/proto"
)

// BenchmarkEntitySize prints the typical proto-serialized size
// of a scheduler, and benchmarks its serialization time.
func BenchmarkEntitySize(b *testing.B) {
	params := Params{
		LabelCorpusSize: 1000,

		LabelsPerWorker: 30,
		Workers:         5000,

		LabelsPerTask: 5,
		Tasks:         100000,
	}

	state := NewSchedulerState(params)

	b.ResetTimer()

	var bytes []byte
	for i := 0; i < b.N; i++ {
		stateProto := state.ToProto()
		bytes, _ = proto.Marshal(stateProto)
	}

	fmt.Printf("proto size: %d bytes\n", len(bytes))
}
