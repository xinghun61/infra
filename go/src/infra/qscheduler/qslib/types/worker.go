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

package types

import "sort"

// IsIdle returns whether the given worker is currently idle.
func (w *Worker) IsIdle() bool {
	return w.RunningTask == nil
}

// SortAscendingCost sorts a slice in-place by ascending cost.
func SortAscendingCost(ws []*Worker) {
	less := func(i, j int) bool {
		return ws[i].RunningTask.Cost.Less(*ws[j].RunningTask.Cost)
	}
	sort.SliceStable(ws, less)
}

// SortDescendingCost sorts a slice in-place by descending cost.
func SortDescendingCost(ws []*Worker) {
	less := func(i, j int) bool {
		return ws[j].RunningTask.Cost.Less(*ws[i].RunningTask.Cost)
	}
	sort.SliceStable(ws, less)
}
