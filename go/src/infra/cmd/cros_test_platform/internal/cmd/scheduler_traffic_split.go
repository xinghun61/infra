// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"context"
	"fmt"
	"strings"

	"go.chromium.org/chromiumos/infra/proto/go/test_platform"

	"infra/cmd/cros_test_platform/internal/site"
	"infra/cmd/cros_test_platform/internal/trafficsplit"

	"github.com/maruel/subcommands"
	"go.chromium.org/chromiumos/infra/proto/go/test_platform/config"
	"go.chromium.org/chromiumos/infra/proto/go/test_platform/migration/scheduler"
	"go.chromium.org/chromiumos/infra/proto/go/test_platform/steps"
	"go.chromium.org/luci/auth/client/authcli"
	"go.chromium.org/luci/common/api/gitiles"
	"go.chromium.org/luci/common/cli"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/logging"
	gitilespb "go.chromium.org/luci/common/proto/gitiles"
)

// SchedulerTrafficSplit implements the `scheduler-traffic-split` subcommand.
var SchedulerTrafficSplit = &subcommands.Command{
	UsageLine: "scheduler-traffic-split -input_json /path/to/input.json -output_json /path/to/output.json",
	ShortDesc: "Determine traffic split between backend schedulers.",
	LongDesc: `Determine traffic split between backend schedulers, i.e. Autotest vs Skylab.

Step input and output is JSON encoded protobuf defined at
https://chromium.googlesource.com/chromiumos/infra/proto/+/master/src/test_platform/steps/scheduler_traffic_split.proto`,
	CommandRun: func() subcommands.CommandRun {
		c := &schedulerTrafficSplitRun{}
		c.authFlags.Register(&c.Flags, site.DefaultAuthOptions)
		c.Flags.StringVar(&c.inputPath, "input_json", "", "Path that contains JSON encoded test_platform.steps.SchedulerTrafficSplitRequest")
		c.Flags.StringVar(&c.outputPath, "output_json", "", "Path where JSON encoded test_platform.steps.SchedulerTrafficSplitResponse should be written.")
		return c
	},
}

type schedulerTrafficSplitRun struct {
	subcommands.CommandRunBase
	authFlags authcli.Flags

	inputPath  string
	outputPath string
}

func (c *schedulerTrafficSplitRun) Run(a subcommands.Application, args []string, env subcommands.Env) int {
	err := c.innerRun(a, args, env)
	if err != nil {
		fmt.Fprintf(a.GetErr(), "%s\n", err)
	}
	return exitCode(err)
}

func (c *schedulerTrafficSplitRun) innerRun(a subcommands.Application, args []string, env subcommands.Env) error {
	if err := c.processCLIArgs(args); err != nil {
		return err
	}
	var request steps.SchedulerTrafficSplitRequest
	if err := readRequest(c.inputPath, &request); err != nil {
		return err
	}

	ctx := cli.GetContext(a, c, env)
	ctx = setupLogging(ctx)

	split, err := c.getTrafficSplitConfig(ctx, request.Config)
	if err != nil {
		return err
	}
	resp, err := trafficsplit.ApplyToRequest(request.Request, split)
	if err != nil {
		logPotentiallyRelevantRules(ctx, request.Request, split.Rules)
		return err
	}
	return writeResponse(c.outputPath, resp)
}

func (c *schedulerTrafficSplitRun) processCLIArgs(args []string) error {
	if len(args) > 0 {
		return errors.Reason("have %d positional args, want 0", len(args)).Err()
	}
	if c.inputPath == "" {
		return errors.Reason("-input_json not specified").Err()
	}
	if c.outputPath == "" {
		return errors.Reason("-output_json not specified").Err()
	}
	return nil
}

func (c *schedulerTrafficSplitRun) getTrafficSplitConfig(ctx context.Context, config *config.Config_SchedulerMigration) (*scheduler.TrafficSplit, error) {
	g, err := c.newGitilesClient(ctx, config.GitilesHost)
	if err != nil {
		return nil, errors.Annotate(err, "get traffic split config").Err()
	}
	text, err := c.downloadTrafficSplitConfig(ctx, g, config)
	if err != nil {
		return nil, errors.Annotate(err, "get traffic split config").Err()
	}
	var split scheduler.TrafficSplit
	if err := unmarshaller.Unmarshal(strings.NewReader(text), &split); err != nil {
		return nil, errors.Annotate(err, "get traffic split config").Err()
	}
	return &split, nil
}

func (c *schedulerTrafficSplitRun) newGitilesClient(ctx context.Context, host string) (gitilespb.GitilesClient, error) {
	h, err := newAuthenticatedHTTPClient(ctx, &c.authFlags)
	if err != nil {
		return nil, errors.Annotate(err, "new gitiles client").Err()
	}
	return gitiles.NewRESTClient(h, host, true)
}

// downloadTrafficSplitConfig returns the contents of the config downloaded from Gitiles.
func (c *schedulerTrafficSplitRun) downloadTrafficSplitConfig(ctx context.Context, client gitilespb.GitilesClient, config *config.Config_SchedulerMigration) (string, error) {
	res, err := client.DownloadFile(ctx, &gitilespb.DownloadFileRequest{
		Project:    config.GitProject,
		Committish: config.Commitish,
		Path:       config.FilePath,
		Format:     gitilespb.DownloadFileRequest_TEXT,
	})
	if err != nil {
		return "", errors.Annotate(err, "download from gitiles").Err()
	}
	return res.Contents, nil
}

func logPotentiallyRelevantRules(ctx context.Context, request *test_platform.Request, rules []*scheduler.Rule) {
	f := trafficsplit.NewRuleFilter(rules)
	logger := logging.Get(ctx)
	logger.Warningf("No matching rule found. Printing partially matching rules...")

	m := request.GetParams().GetHardwareAttributes().GetModel()
	if pr := f.ForModel(m); len(pr) > 0 {
		logger.Infof("Following rules match requested model: %s", formatFirstFewRules(pr))
	} else {
		logger.Warningf("No rules matched requested model %s.", m)
	}

	b := request.GetParams().GetSoftwareAttributes().GetBuildTarget().GetName()
	if pr := f.ForBuildTarget(b); len(pr) > 0 {
		logger.Infof("Following rules match requested buildTarget: %s", formatFirstFewRules(pr))
	} else {
		logger.Warningf("No rules matched requested build target %s.", b)
	}

	s := request.GetParams().GetScheduling()
	if pr := f.ForScheduling(s); len(pr) > 0 {
		logger.Infof("Following rules match requested scheduling: %s", formatFirstFewRules(pr))
	} else {
		logger.Warningf("No rules matched requested scheduling %s.", s)
	}
}

func formatFirstFewRules(rules []*scheduler.Rule) string {
	const rulesToPrint = 5
	s := fmt.Sprintf("%v", rules[:rulesToPrint])
	if len(s) > rulesToPrint {
		s = fmt.Sprintf("%s... [%d more]", s, len(s)-rulesToPrint)
	}
	return s
}
