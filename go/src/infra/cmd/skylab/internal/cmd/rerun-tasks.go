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

	"github.com/maruel/subcommands"
	"go.chromium.org/luci/auth/client/authcli"
	swarming "go.chromium.org/luci/common/api/swarming/swarming/v1"
	"go.chromium.org/luci/common/cli"
	"go.chromium.org/luci/common/errors"

	"infra/cmd/skylab/internal/site"
)

// RerunTasks subcommand.
var RerunTasks = &subcommands.Command{
	UsageLine: "rerun-tasks [TASK_ID...]",
	ShortDesc: "create copies of tasks to run again",
	LongDesc:  `Create copies of tasks to run again.`,
	CommandRun: func() subcommands.CommandRun {
		c := &rerunTasksRun{}
		c.authFlags.Register(&c.Flags, site.DefaultAuthOptions)
		c.envFlags.Register(&c.Flags)
		c.Flags.BoolVar(&c.outputJSON, "output-json", false, "Format output as JSON.")
		return c
	},
}

type rerunTasksRun struct {
	subcommands.CommandRunBase
	authFlags  authcli.Flags
	envFlags   envFlags
	outputJSON bool
}

func (c *rerunTasksRun) Run(a subcommands.Application, args []string, env subcommands.Env) int {
	if err := c.innerRun(a, args, env); err != nil {
		PrintError(a.GetErr(), err)
		return 1
	}
	return 0
}

func (c *rerunTasksRun) innerRun(a subcommands.Application, args []string, env subcommands.Env) error {
	if c.Flags.NArg() == 0 {
		return NewUsageError(c.Flags, "missing task ID")
	}
	originalIDs := c.Flags.Args()
	siteEnv := c.envFlags.Env()
	ctx := cli.GetContext(a, c, env)
	s, err := newSwarmingService(ctx, c.authFlags, siteEnv)
	if err != nil {
		return err
	}

	originalRequests, err := getSwarmingRequestsForIds(ctx, originalIDs, s)
	if err != nil {
		return err
	}

	ctx, cf := context.WithTimeout(ctx, 60*time.Second)
	defer cf()
	originalToRerunID := make(map[string]string)
	for i, original := range originalRequests {
		originalID := originalIDs[i]
		newRequest, err := createRerunRequest(original, originalID, siteEnv)
		if err != nil {
			return errors.Annotate(err, fmt.Sprintf("rerun task %s", originalID)).Err()
		}

		resp, err := s.Tasks.New(newRequest).Context(ctx).Do()
		if err != nil {
			return errors.Annotate(err, fmt.Sprintf("rerun task %s", originalID)).Err()
		}
		originalToRerunID[originalID] = resp.TaskId
	}

	if c.outputJSON {
		return printJSONMap(a.GetOut(), originalToRerunID, siteEnv)
	}

	return printIDMap(a.GetOut(), originalToRerunID, siteEnv)
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
	original.Tags = upsertTag(original.Tags, "skylab-tool", "rerun-tasks")
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
