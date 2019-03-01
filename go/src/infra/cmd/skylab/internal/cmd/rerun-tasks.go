// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"bufio"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"strings"
	"time"

	"go.chromium.org/luci/common/data/stringset"

	"github.com/maruel/subcommands"
	"go.chromium.org/luci/auth/client/authcli"
	swarming "go.chromium.org/luci/common/api/swarming/swarming/v1"
	"go.chromium.org/luci/common/cli"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/flag"

	"infra/cmd/skylab/internal/site"
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
		c.Flags.BoolVar(&c.dryRun, "dry-run", false, "Print tasks that would be rerun, but don't actually rerun them.")
		return c
	},
}

type rerunTasksRun struct {
	subcommands.CommandRunBase
	authFlags  authcli.Flags
	envFlags   envFlags
	outputJSON bool
	taskIds    []string
	tags       []string
	dryRun     bool
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

	s, err := newSwarmingService(ctx, c.authFlags, siteEnv)
	if err != nil {
		return err
	}

	var originalTasks []*swarming.SwarmingRpcsTaskResult
	if len(c.taskIds) > 0 {
		if originalTasks, err = getSwarmingResultsForIds(ctx, c.taskIds, s); err != nil {
			return err
		}
	} else {
		if originalTasks, err = getSwarmingResultsForTags(ctx, c.tags, s); err != nil {
			return err
		}
	}

	printTaskInfo(originalTasks, siteEnv)
	if answer := prompt(fmt.Sprintf("Do you want to rerun %d tasks? [y/N] > ", len(originalTasks))); !answer {
		return errors.New("user cancelled")
	}

	originalIDs := make([]string, len(originalTasks))
	for i, r := range originalTasks {
		originalIDs[i] = r.TaskId
	}
	originalRequests, err := getSwarmingRequestsForIds(ctx, originalIDs, s)
	if err != nil {
		return err
	}

	newRequests, err := getNewRequests(originalIDs, originalRequests, siteEnv)
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
		resp, err := s.Tasks.New(r).Context(ctx).Do()
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

func printTaskInfo(results []*swarming.SwarmingRpcsTaskResult, siteEnv site.Environment) {
	fmt.Println(strings.Repeat("-", 80))
	fmt.Printf("Found %d tasks to rerun:\n", len(results))
	for i, r := range results {
		if i < showTaskLimit {
			fmt.Printf("%s\n", swarmingTaskURL(siteEnv, r.TaskId))
		} else {
			break
		}
	}
	if len(results) > showTaskLimit {
		fmt.Printf("... and %d more tasks\n", len(results)-showTaskLimit)
	}
	fmt.Println(strings.Repeat("-", 80))
}

func prompt(s string) bool {
	fmt.Fprintf(os.Stderr, s)
	reader := bufio.NewReader(os.Stdin)
	answer, _ := reader.ReadString('\n')
	answer = strings.TrimSpace(answer)
	return answer == "y" || answer == "Y"
}

func getSwarmingResultsForIds(ctx context.Context, IDs []string, s *swarming.Service) ([]*swarming.SwarmingRpcsTaskResult, error) {
	ctx, cf := context.WithTimeout(ctx, 60*time.Second)
	defer cf()
	results := make([]*swarming.SwarmingRpcsTaskResult, len(IDs))
	for i, ID := range IDs {
		r, err := s.Task.Result(ID).Context(ctx).Do()
		if err != nil {
			return nil, errors.Annotate(err, fmt.Sprintf("rerun task %s", ID)).Err()
		}
		results[i] = r
	}
	return results, nil
}

func getSwarmingResultsForTags(ctx context.Context, tags []string, s *swarming.Service) ([]*swarming.SwarmingRpcsTaskResult, error) {
	ctx, cf := context.WithTimeout(ctx, 60*time.Second)
	defer cf()
	results, err := s.Tasks.List().Tags(tags...).Context(ctx).Do()
	if err != nil {
		return nil, errors.Annotate(err, fmt.Sprint("rerun tags ", tags)).Err()
	}
	return results.Items, nil
}

func getSwarmingRequestsForIds(ctx context.Context, IDs []string, s *swarming.Service) ([]*swarming.SwarmingRpcsTaskRequest, error) {
	ctx, cf := context.WithTimeout(ctx, 60*time.Second)
	defer cf()
	requests := make([]*swarming.SwarmingRpcsTaskRequest, len(IDs))
	for i, ID := range IDs {
		request, err := s.Task.Request(ID).Context(ctx).Do()
		if err != nil {
			return nil, errors.Annotate(err, fmt.Sprintf("rerun task %s", ID)).Err()
		}
		requests[i] = request
	}
	return requests, nil
}

func getNewRequests(taskIDs []string, originalRequests []*swarming.SwarmingRpcsTaskRequest, siteEnv site.Environment) (map[string]*swarming.SwarmingRpcsNewTaskRequest, error) {
	newRequests := make(map[string]*swarming.SwarmingRpcsNewTaskRequest)
	rerunTag := fmt.Sprintf("%s:%s", rerunTagKey, rerunTagVal)
	for i, original := range originalRequests {
		originalTags := stringset.NewFromSlice(original.Tags...)
		if originalTags.Has(rerunTag) {
			continue
		}

		newRequest, err := createRerunRequest(original, taskIDs[i], siteEnv)
		if err != nil {
			return nil, errors.Annotate(err, fmt.Sprintf("rerun task %s", original.Name)).Err()
		}
		newRequests[taskIDs[i]] = newRequest
	}
	return newRequests, nil
}

// createRerunRequest modifies a request to produce rerun a Skylab task.
func createRerunRequest(original *swarming.SwarmingRpcsTaskRequest, originalID string, siteEnv site.Environment) (*swarming.SwarmingRpcsNewTaskRequest, error) {
	newURL := generateAnnotationURL(siteEnv)
	for _, s := range original.TaskSlices {
		cmd := s.Properties.Command
		if cmd[0] != "/opt/infra-tools/skylab_swarming_worker" {
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

	return newTaskRequest(original.Name, original.Tags, original.TaskSlices, original.Priority), nil
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
			originalID, swarmingTaskURL(siteEnv, rerunID))
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

func dryRun(a subcommands.Application, newRequests map[string]*swarming.SwarmingRpcsNewTaskRequest, siteEnv site.Environment) error {
	for id, r := range newRequests {
		fmt.Fprintf(a.GetOut(), "Would have rerun %s (%s)\n", swarmingTaskURL(siteEnv, id), r.Name)
	}
	return nil
}
