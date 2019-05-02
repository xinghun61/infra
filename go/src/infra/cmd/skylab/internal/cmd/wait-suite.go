// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"github.com/maruel/subcommands"
)

// WaitSuite subcommand: to be deprecated, identical behavior to WaitTask
// TODO(akeshet): Delete this subcommand once all callers are migrated to
// wait-task.
var WaitSuite = &subcommands.Command{
	UsageLine:  "wait-suite [FLAGS...] SWARMING_TASK_ID",
	ShortDesc:  "To be deprecated, identical behavior to wait-task",
	LongDesc:   `To be deprecated, identical behavior to wait-task`,
	CommandRun: WaitTask.CommandRun,
}
