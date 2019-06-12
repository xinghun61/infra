// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"strings"
	"time"

	"go.chromium.org/luci/common/data/stringset"

	"github.com/maruel/subcommands"
	"go.chromium.org/luci/auth/client/authcli"
	swarming_api "go.chromium.org/luci/common/api/swarming/swarming/v1"
	"go.chromium.org/luci/common/cli"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/flag"

	"infra/cmd/skylab/internal/site"
	"infra/libs/skylab/swarming"
	"infra/libs/skylab/worker"
)

const showTaskLimit = 5

const rerunTagKey = "skylab-tool"
const rerunTagVal = "rerun-tasks"

// RerunTasks subcommand.
var RerunTasks = &subcommands.Command{
	UsageLine: "rerun-tasks [-task-id TASK_ID...] [-tag TAG...]",
	ShortDesc: "create copies of tasks to run again",
	LongDesc:  `Create copies of tasks to run again.`,
	CommandRun: func() subcommands.CommandRun {
		c := &rerunTasksRun{}
		c.authFlags.Register(&c.Flags, site.DefaultAuthOptions)
		c.envFlags.Register(&c.Flags)
		c.Flags.BoolVar(&c.outputJSON, "output-json", false, "Format output as JSON.")
		c.Flags.Var(flag.StringSlice(&c.taskIds), "task-id", "Swarming task ids for locating tests to retry. If it's a retry task which is kicked off by rerun-tasks command, it won't be retried. May be specified multiple times.")
		c.Flags.Var(flag.StringSlice(&c.tags), "tag", "Tasks that match all these tags (and that were not already a retry task) will be retried. Task-id and tag cannot be both specified. May be specified multiple times.")
		c.Flags.BoolVar(&c.includePassed, "include-passed", false, "If true, rerun tasks even if they passed the first time. Only apply to tasks matched by tags.")
		c.Flags.BoolVar(&c.dryRun, "dry-run", false, "Print tasks that would be rerun, but don't actually rerun them.")
		c.Flags.BoolVar(&c.preserveParent, "preserve-parent", false, "Preserve the parent task ID of retried tasks. This should be used only within the context of a suite retrying its own children.")
		return c
	},
}

type rerunTasksRun struct {
	subcommands.CommandRunBase
	authFlags      authcli.Flags
	envFlags       envFlags
	outputJSON     bool
	taskIds        []string
	tags           []string
	includePassed  bool
	dryRun         bool
	preserveParent bool
}

func (c *rerunTasksRun) Run(a subcommands.Application, args []string, env subcommands.Env) int {
	if err := c.innerRun(a, args, env); err != nil {
		PrintError(a.GetErr(), err)
		return 1
	}
	return 0
}

func (c *rerunTasksRun) innerRun(a subcommands.Application, args []string, env subcommands.Env) error {
	if len(c.taskIds) == 0 && len(c.tags) == 0 {
		return NewUsageError(c.Flags, "missing task ID or task tags")
	}

	if len(c.taskIds) > 0 && len(c.tags) > 0 {
		return NewUsageError(c.Flags, "Cannot specify -task-id and -tag together")
	}

	siteEnv := c.envFlags.Env()
	ctx := cli.GetContext(a, c, env)
	h, err := httpClient(ctx, &c.authFlags)
	if err != nil {
		return errors.Annotate(err, "failed to create http client").Err()
	}
	client, err := swarming.New(ctx, h, siteEnv.SwarmingService)
	if err != nil {
		return err
	}

	var originalTasks []*swarming_api.SwarmingRpcsTaskResult
	if len(c.taskIds) > 0 {
		if originalTasks, err = client.GetResults(ctx, c.taskIds); err != nil {
			return err
		}
	} else {
		if originalTasks, err = client.GetResultsForTags(ctx, c.tags); err != nil {
			return err
		}
		if !c.includePassed {
			originalTasks = filterPassedRequests(originalTasks)
		}
	}

	printTaskInfo(originalTasks, showTaskLimit, "rerun", siteEnv)
	if answer := prompt(fmt.Sprintf("Do you want to rerun %d tasks? [y/N] > ", len(originalTasks))); !answer {
		return errors.New("user cancelled")
	}

	originalIDs := make([]string, len(originalTasks))
	for i, r := range originalTasks {
		originalIDs[i] = r.TaskId
	}
	originalRequests, err := client.GetRequests(ctx, originalIDs)
	if err != nil {
		return err
	}

	newRequests, err := getNewRequests(originalIDs, originalRequests, c.preserveParent, siteEnv)
	if err != nil {
		return err
	}

	if c.dryRun {
		return dryRun(a, newRequests, siteEnv)
	}

	ctx, cf := context.WithTimeout(ctx, 60*time.Second)
	defer cf()
	originalToRerunID := make(map[string]string)
	for id, r := range newRequests {
		resp, err := client.CreateTask(ctx, r)
		if err != nil {
			return errors.Annotate(err, fmt.Sprintf("rerun task %s", id)).Err()
		}
		originalToRerunID[id] = resp.TaskId
	}

	if c.outputJSON {
		return printJSONMap(a.GetOut(), originalToRerunID, siteEnv)
	}

	return printIDMap(a.GetOut(), originalToRerunID, siteEnv)
}

// filterPassedResults removes result items for passed tasks.
func filterPassedRequests(results []*swarming_api.SwarmingRpcsTaskResult) []*swarming_api.SwarmingRpcsTaskResult {
	filtered := make([]*swarming_api.SwarmingRpcsTaskResult, 0, len(results))
	for _, r := range results {
		// Failure includes: COMPLETED_FAILURE (test failure), TIMED OUT
		// Internal Failure includes: BOT_DIED
		// Tasks in CANCELED, NO_RESOURCE, EXPIRED are skipped (won't be rerun)
		if r.Failure || r.InternalFailure {
			filtered = append(filtered, r)
		}
	}
	return filtered
}

func getNewRequests(taskIDs []string, originalRequests []*swarming_api.SwarmingRpcsTaskRequest, preserveParent bool, siteEnv site.Environment) (map[string]*swarming_api.SwarmingRpcsNewTaskRequest, error) {
	newRequests := make(map[string]*swarming_api.SwarmingRpcsNewTaskRequest)
	rerunTag := fmt.Sprintf("%s:%s", rerunTagKey, rerunTagVal)
	for i, original := range originalRequests {
		originalTags := stringset.NewFromSlice(original.Tags...)
		if originalTags.Has(rerunTag) {
			continue
		}

		newRequest, err := createRerunRequest(original, taskIDs[i], preserveParent, siteEnv)
		if err != nil {
			return nil, errors.Annotate(err, fmt.Sprintf("rerun task %s", original.Name)).Err()
		}
		newRequests[taskIDs[i]] = newRequest
	}
	return newRequests, nil
}

// createRerunRequest modifies a request to produce rerun a Skylab task.
func createRerunRequest(original *swarming_api.SwarmingRpcsTaskRequest, originalID string, preserveParent bool, siteEnv site.Environment) (*swarming_api.SwarmingRpcsNewTaskRequest, error) {
	newURL := worker.GenerateLogDogURL(siteEnv.Wrapped())
	for _, s := range original.TaskSlices {
		cmd := s.Properties.Command
		if cmd[0] != worker.DefaultPath {
			return nil, fmt.Errorf("task was not a Skylab task")
		}

		for j, c := range cmd {
			if c == "-logdog-annotation-url" {
				cmd[j+1] = newURL
			}
		}
	}

	original.Tags = upsertTag(original.Tags, "log_location", newURL)
	original.Tags = upsertTag(original.Tags, rerunTagKey, rerunTagVal)
	original.Tags = upsertTag(original.Tags, "retry_original_task_id", originalID)

	var parentTaskID string
	// TODO(akeshet): If preserveParent is false, we should also drop any
	// parent_task_id:XXX tag that exists on the original task. Taking that as
	// followup because the tag is an informal API used by run_suite_skylab when
	// it creates tasks, to make then searchable. First it should be turned into
	// a real API enforced by skylab create-test.
	if preserveParent {
		parentTaskID = original.ParentTaskId
	}

	return &swarming_api.SwarmingRpcsNewTaskRequest{
		Name:         original.Name,
		Tags:         original.Tags,
		TaskSlices:   original.TaskSlices,
		ParentTaskId: parentTaskID,
		Priority:     original.Priority,
	}, nil
}

func upsertTag(tags []string, key string, replacementValue string) []string {
	replacementTag := key + ":" + replacementValue
	for i, t := range tags {
		if strings.HasPrefix(t, key) {
			tags[i] = replacementTag
			return tags
		}
	}
	return append(tags, replacementTag)
}

func printIDMap(w io.Writer, originalToRerunID map[string]string, siteEnv site.Environment) error {
	for originalID, rerunID := range originalToRerunID {
		fmt.Fprintf(w, "Rerunning %s\tCreated Swarming task %s\n",
			originalID, swarming.TaskURL(siteEnv.SwarmingService, rerunID))
	}

	return nil
}

func printJSONMap(w io.Writer, originalToRerunID map[string]string, siteEnv site.Environment) error {
	outputMap := map[string]map[string]string{
		"original_id_to_rerun_id_map": originalToRerunID,
	}

	outputJSON, err := json.Marshal(outputMap)
	if err != nil {
		return err
	}

	fmt.Fprintf(w, string(outputJSON))

	return nil
}

func dryRun(a subcommands.Application, newRequests map[string]*swarming_api.SwarmingRpcsNewTaskRequest, siteEnv site.Environment) error {
	for id, r := range newRequests {
		fmt.Fprintf(a.GetOut(), "Would have rerun %s (%s)\n", swarming.TaskURL(siteEnv.SwarmingService, id), r.Name)
	}
	return nil
}
