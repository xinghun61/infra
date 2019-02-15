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
	"sort"
)

// sortAscendingCost sorts a slice in-place by ascending cost.
func sortAscendingCost(ws []*Worker) {
	less := func(i, j int) bool {
		return less(ws[i].runningTask.cost, ws[j].runningTask.cost)
	}
	sort.SliceStable(ws, less)
}

// sortDescendingCost sorts a slice in-place by descending cost.
func sortDescendingCost(ws []*Worker) {
	less := func(i, j int) bool {
		return less(ws[j].runningTask.cost, ws[i].runningTask.cost)
	}
	sort.SliceStable(ws, less)
}

func less(a Balance, b Balance) bool {
	for i := range a {
		if a[i] < b[i] {
			return true
		}
		if b[i] < a[i] {
			return false
		}
	}
	return false
}
