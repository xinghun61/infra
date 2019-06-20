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

package cron

import (
	"go.chromium.org/luci/common/tsmon/field"
	"go.chromium.org/luci/common/tsmon/metric"
)

var (
	freeInvalidDUTsTick = metric.NewCounter(
		"chromeos/drone-queen/cron/free-invalid-duts/success",
		"success of free-invalid-duts cron jobs",
		nil,
		field.String("instance"),
		field.Bool("success"),
	)
	pruneExpiredDronesTick = metric.NewCounter(
		"chromeos/drone-queen/cron/prune-expired-drones/success",
		"success of prune-expired-drones cron jobs",
		nil,
		field.String("instance"),
		field.Bool("success"),
	)
	pruneDrainedDUTsTick = metric.NewCounter(
		"chromeos/drone-queen/cron/prune-drained-duts/success",
		"success of prune-drained-duts cron jobs",
		nil,
		field.String("instance"),
		field.Bool("success"),
	)
)
