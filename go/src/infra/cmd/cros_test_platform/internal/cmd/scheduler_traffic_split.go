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

	"github.com/golang/protobuf/proto"
	"github.com/maruel/subcommands"
	"go.chromium.org/chromiumos/infra/proto/go/test_platform/migration/scheduler"
	"go.chromium.org/chromiumos/infra/proto/go/test_platform/steps"
	"go.chromium.org/luci/auth/client/authcli"
	"go.chromium.org/luci/common/api/gitiles"
	"go.chromium.org/luci/common/cli"
	"go.chromium.org/luci/common/errors"
	gitilespb "go.chromium.org/luci/common/proto/gitiles"
)

// TODO(pprabhu) Move these constants to cros_test_platform common Config.
const (
	migrationConfigGitilesHost = "chrome-internal.googlesource.com"
	migrationConfigGitProject  = "chromeos/infra/config"
	migrationConfigFilePath    = "testplatform/generated/scheduler_migration.cfg"
	migrationConfigCommittish  = "refs/heads/master"
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

	split, err := c.getTrafficSplitConfig(ctx)
	if err != nil {
		return err
	}
	resp, err := determineTrafficSplit(&request, split)
	if err != nil {
		return err
	}
	return writeResponse(c.outputPath, resp, nil)
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

func (c *schedulerTrafficSplitRun) getTrafficSplitConfig(ctx context.Context) (*scheduler.TrafficSplit, error) {
	g, err := c.newGitilesClient(ctx)
	if err != nil {
		return nil, errors.Annotate(err, "get traffic split config").Err()
	}
	text, err := c.downloadTrafficSplitConfig(ctx, g)
	if err != nil {
		return nil, errors.Annotate(err, "get traffic split config").Err()
	}
	var split scheduler.TrafficSplit
	if err := unmarshaller.Unmarshal(strings.NewReader(text), &split); err != nil {
		return nil, errors.Annotate(err, "get traffic split config").Err()
	}
	return &split, nil
}

func (c *schedulerTrafficSplitRun) newGitilesClient(ctx context.Context) (gitilespb.GitilesClient, error) {
	h, err := newAuthenticatedHTTPClient(ctx, &c.authFlags)
	if err != nil {
		return nil, errors.Annotate(err, "new gitiles client").Err()
	}
	return gitiles.NewRESTClient(h, migrationConfigGitilesHost, true)
}

// downloadTrafficSplitConfig returns the contents of the config downloaded from Gitiles.
func (c *schedulerTrafficSplitRun) downloadTrafficSplitConfig(ctx context.Context, client gitilespb.GitilesClient) (string, error) {
	res, err := client.DownloadFile(ctx, &gitilespb.DownloadFileRequest{
		Project:    migrationConfigGitProject,
		Committish: migrationConfigCommittish,
		Path:       migrationConfigFilePath,
		Format:     gitilespb.DownloadFileRequest_TEXT,
	})
	if err != nil {
		return "", errors.Annotate(err, "download from gitiles").Err()
	}
	return res.Contents, nil
}

func determineTrafficSplit(request *steps.SchedulerTrafficSplitRequest, trafficSplitConfig *scheduler.TrafficSplit) (*steps.SchedulerTrafficSplitResponse, error) {
	if err := ensureSufficientForTrafficSplit(request.Request); err != nil {
		return nil, errors.Annotate(err, "determine traffic split").Err()
	}
	rules := determineRelevantRules(request.Request, trafficSplitConfig.Rules)
	switch {
	case len(rules) == 0:
		return nil, errors.Reason("no matching traffic split rule").Err()
	case len(rules) > 1:
		return nil, errors.Reason("too many matching traffic split rules %s for request %s", rules, request).Err()
	default:
		// good case fallthrough.
	}
	return applyTrafficSplitRule(request, rules[0])
}

func ensureSufficientForTrafficSplit(r *test_platform.Request) error {
	if r.GetParams().GetScheduling().GetPool() == nil {
		return errors.Reason("request contains no pool information").Err()
	}
	return nil
}

func applyTrafficSplitRule(request *steps.SchedulerTrafficSplitRequest, rule *scheduler.Rule) (*steps.SchedulerTrafficSplitResponse, error) {
	newRequest := applyRequestModification(request.Request, rule.GetRequestMod())
	switch rule.Backend {
	case scheduler.Backend_BACKEND_AUTOTEST:
		return &steps.SchedulerTrafficSplitResponse{
			AutotestRequest: newRequest,
		}, nil
	case scheduler.Backend_BACKEND_SKYLAB:
		return &steps.SchedulerTrafficSplitResponse{
			SkylabRequest: newRequest,
		}, nil
	default:
		return nil, errors.Reason("invalid backend %s in rule", rule.Backend.String()).Err()
	}
}

func applyRequestModification(request *test_platform.Request, mod *scheduler.RequestMod) *test_platform.Request {
	if mod == nil {
		return request
	}
	var dst test_platform.Request
	proto.Merge(&dst, request)
	if dst.Params == nil {
		dst.Params = &test_platform.Request_Params{}
	}
	proto.Merge(dst.Params.Scheduling, mod.Scheduling)
	return &dst
}

func determineRelevantRules(request *test_platform.Request, rules []*scheduler.Rule) []*scheduler.Rule {
	ret := []*scheduler.Rule{}
	for _, r := range rules {
		if isRuleRelevant(request, r) {
			ret = append(ret, r)
		}
	}
	return ret
}

func isRuleRelevant(request *test_platform.Request, rule *scheduler.Rule) bool {
	if isNonEmptyAndDistinct(
		request.GetParams().GetSoftwareAttributes().GetBuildTarget().GetName(),
		rule.GetRequest().GetBuildTarget().GetName(),
	) {
		return false
	}
	if isNonEmptyAndDistinct(
		request.GetParams().GetHardwareAttributes().GetModel(),
		rule.GetRequest().GetModel(),
	) {
		return false
	}
	return isSchedulingRelevant(request.GetParams().GetScheduling(), rule.GetRequest().GetScheduling())
}

func isSchedulingRelevant(got, want *test_platform.Request_Params_Scheduling) bool {
	if isNonEmptyAndDistinct(got.GetUnmanagedPool(), want.GetUnmanagedPool()) {
		return false
	}
	if isNonEmptyAndDistinct(got.GetManagedPool().String(), want.GetManagedPool().String()) {
		return false
	}
	if isNonEmptyAndDistinct(got.GetQuotaAccount(), want.GetQuotaAccount()) {
		return false
	}
	return true
}

func isNonEmptyAndDistinct(got, want string) bool {
	return got != "" && got != want
}
