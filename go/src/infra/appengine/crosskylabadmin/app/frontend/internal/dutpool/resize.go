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

package dutpool

import (
	"fmt"
	fleet "infra/appengine/crosskylabadmin/api/fleet/v1"
	"infra/libs/skylab/inventory"

	"go.chromium.org/luci/common/errors"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

// Resize returns the inventory changes required to resize the targetPool to be
// of targetSize, using sparePool to borrow / return DUTs.
func Resize(duts []*inventory.DeviceUnderTest, targetPool string, targetSize int, sparePool string) ([]*fleet.PoolChange, error) {
	errStr := fmt.Sprintf("resizePool %s pool to %d DUTs using %s spare pool", targetPool, targetSize, sparePool)
	dp, err := mapPoolsToDUTs(duts)
	if err != nil {
		return []*fleet.PoolChange{}, errors.Annotate(err, errStr).Err()
	}

	ts := dp[targetPool]
	ss := dp[sparePool]
	switch {
	case len(ts) < targetSize:
		want := targetSize - len(ts)
		if want > len(ss) {
			return []*fleet.PoolChange{}, status.Errorf(codes.ResourceExhausted, "%s: insufficient spares (want %d, have %d)", errStr, want, len(ss))
		}
		return changeDUTPools(ss[:want], sparePool, targetPool), nil
	case len(ts) > targetSize:
		return changeDUTPools(ts[:len(ts)-targetSize], targetPool, sparePool), nil
	default:
		// targetPool is already the right size.
		return []*fleet.PoolChange{}, nil
	}
}
