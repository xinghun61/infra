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

// Package tutils provides convenience functions to convert between proto representations
// and time.Time / time.Duration representations of times or durations.
package tutils

import (
	"time"

	"github.com/golang/protobuf/ptypes"
	"github.com/golang/protobuf/ptypes/duration"
	"github.com/golang/protobuf/ptypes/timestamp"
)

// Duration coverts a duration proto to a time.Duration, and panics if there's an error.
func Duration(d *duration.Duration) time.Duration {
	ans, err := ptypes.Duration(d)
	if err != nil {
		panic(err)
	}
	return ans
}

// DurationProto coverts a time.Duration to proto.
func DurationProto(d time.Duration) *duration.Duration {
	return ptypes.DurationProto(d)
}

// Timestamp converts a timestamp proto to a time.Time, and panics if there's an error.
func Timestamp(t *timestamp.Timestamp) time.Time {
	ans, err := ptypes.Timestamp(t)
	if err != nil {
		panic(err)
	}
	return ans
}

// TimestampProto converts a time.Time proto to a timestamp proto, and panics if there's an error.
func TimestampProto(t time.Time) *timestamp.Timestamp {
	ans, err := ptypes.TimestampProto(t)
	if err != nil {
		panic(err)
	}
	return ans
}
