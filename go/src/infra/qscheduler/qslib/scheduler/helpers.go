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

	"infra/qscheduler/qslib/types"
)

// workerWithId is a (Worker, Id) tuple.
type workerWithId struct {
	Worker *types.Worker
	Id     string
}

// sortAscendingCost sorts a slice in-place by ascending cost.
func sortAscendingCost(ws []workerWithId) {
	less := func(i, j int) bool {
		return ws[i].Worker.RunningTask.Cost.Less(*ws[j].Worker.RunningTask.Cost)
	}
	sort.SliceStable(ws, less)
}

// sortDescendingCost sorts a slice in-place by descending cost.
func sortDescendingCost(ws []workerWithId) {
	less := func(i, j int) bool {
		return ws[j].Worker.RunningTask.Cost.Less(*ws[i].Worker.RunningTask.Cost)
	}
	sort.SliceStable(ws, less)
}
