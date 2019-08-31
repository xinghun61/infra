// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"context"
	"fmt"
	"os"
	"sort"
	"strings"

	structpb "github.com/golang/protobuf/ptypes/struct"
	"github.com/maruel/subcommands"
	"go.chromium.org/luci/auth/client/authcli"
	buildbucketpb "go.chromium.org/luci/buildbucket/proto"
	"go.chromium.org/luci/common/cli"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/flag"
	"go.chromium.org/luci/common/logging"

	"infra/cmd/skylab/internal/bb"
	"infra/cmd/skylab/internal/site"
	"infra/cmd/skylab/internal/userinput"
)

// BackfillRequest subcommand: Backfill unsuccessful results for a previous
// request.
var BackfillRequest = &subcommands.Command{
	UsageLine: `backfill-request [FLAGS...]`,
	ShortDesc: "backfill unsuccessful results for a previous request",
	LongDesc: `Backfill unsuccessful results for a previous request.

This command creates a new cros_test_platform request to backfill results from
unsuccessful (expired, timed out, or failed) tasks from a previous build.

The backfill request uses the same parameters as the original request (model,
pool, build etc.). The backfill request attempts to minimize unnecessary task
execution by skipping tasks that have succeeded previously when possible.

This command does not wait for the build to start running.`,
	CommandRun: func() subcommands.CommandRun {
		c := &backfillRequestRun{}
		c.authFlags.Register(&c.Flags, site.DefaultAuthOptions)
		c.envFlags.Register(&c.Flags)
		c.Flags.Int64Var(&c.buildID, "id", -1, "Search for original build with this ID. Mutually exclusive with -tag.")
		c.Flags.Var(flag.StringSlice(&c.buildTags), "tag", "Search for original build matching given tag. May be used multiple times to provide more tags to match. Mutually exclusive with -id")
		return c
	},
}

type backfillRequestRun struct {
	subcommands.CommandRunBase
	authFlags authcli.Flags
	envFlags  envFlags

	buildID   int64
	buildTags []string

	bbClient *bb.Client
}

func (c *backfillRequestRun) Run(a subcommands.Application, args []string, env subcommands.Env) int {
	if err := c.innerRun(a, args, env); err != nil {
		PrintError(a.GetErr(), err)
		return 1
	}
	return 0
}

func (c *backfillRequestRun) innerRun(a subcommands.Application, args []string, env subcommands.Env) error {
	if err := c.validateArgs(); err != nil {
		return err
	}
	ctx := cli.GetContext(a, c, env)
	if err := c.setNewBBClient(ctx); err != nil {
		return err
	}

	originalBuilds, err := c.getOriginalBuilds(ctx)
	if err != nil {
		return err
	}

	switch {
	case len(originalBuilds) == 0:
		return errors.Reason("no matching build found").Err()
	case len(originalBuilds) > 1:
		if !c.confirmMultileBuildsOK(a, originalBuilds) {
			return nil
		}
	default:
	}

	var merr errors.MultiError
	for _, b := range originalBuilds {
		latest, err := c.getLatestBackfillBuildFor(ctx, b)
		if err != nil {
			logging.Errorf(ctx, "Failed to find existing backfill requests for %s: %s", b, err)
			merr = append(merr, err)
			continue
		}
		if latest == nil {
			latest = b
		}

		if isInFlight(latest) {
			logging.Infof(ctx, "Build %s already in flight to backfill %s", c.bbClient.BuildURL(latest.ID), c.bbClient.BuildURL(b.ID))
			continue
		}

		id, err := c.scheduleBackfillBuild(ctx, latest)
		if err != nil {
			logging.Errorf(ctx, "Failed to create backfill request for %s: %s", b, err)
			merr = append(merr, err)
			continue
		}
		logging.Infof(ctx, "Scheduled %s to backfill %s", c.bbClient.BuildURL(id), c.bbClient.BuildURL(b.ID))

	}
	return merr.First()
}

func isInFlight(b *bb.Build) bool {
	return b.Status == buildbucketpb.Status_SCHEDULED || b.Status == buildbucketpb.Status_STARTED
}

// validateArgs ensures that the command line arguments are
func (c *backfillRequestRun) validateArgs() error {
	if c.Flags.NArg() != 0 {
		return NewUsageError(c.Flags, fmt.Sprintf("got %d positional arguments, want 0", c.Flags.NArg()))
	}
	switch {
	case c.isBuildIDSet() && c.isBuildTagsSet():
		return NewUsageError(c.Flags, "use only one of -id and -tag")
	case !(c.isBuildIDSet() || c.isBuildTagsSet()):
		return NewUsageError(c.Flags, "must use one of -id or -tag")
	}
	return nil
}

func (c *backfillRequestRun) isBuildIDSet() bool {
	// The default value of -1 is nonsensical.
	return c.buildID > 0
}

func (c *backfillRequestRun) isBuildTagsSet() bool {
	return len(c.buildTags) > 0
}

func (c *backfillRequestRun) setNewBBClient(ctx context.Context) error {
	client, err := bb.NewClient(ctx, c.envFlags.Env(), c.authFlags)
	if err == nil {
		c.bbClient = client
	}
	return err
}

func (c *backfillRequestRun) getOriginalBuilds(ctx context.Context) ([]*bb.Build, error) {
	if c.isBuildIDSet() {
		b, err := c.getOriginalBuildByID(ctx)
		return []*bb.Build{b}, err
	}
	return c.getOriginalBuildsByTags(ctx)
}

func (c *backfillRequestRun) getOriginalBuildByID(ctx context.Context) (*bb.Build, error) {
	b, err := c.bbClient.GetBuild(ctx, c.buildID)
	if err != nil {
		return nil, err
	}
	if isBackfillBuild(b) {
		return nil, errors.Reason("build ID %d is a backfill build", c.buildID).Err()
	}
	return b, nil
}

func isBackfillBuild(b *bb.Build) bool {
	for _, t := range b.Tags {
		if strings.HasPrefix(t, "backfill:") {
			return true
		}
	}
	return false
}

const bbBuildSearchLimit = 100

func (c *backfillRequestRun) getOriginalBuildsByTags(ctx context.Context) ([]*bb.Build, error) {
	builds, err := c.bbClient.SearchBuildsByTags(ctx, bbBuildSearchLimit, c.buildTags...)
	if err != nil {
		return nil, err
	}
	return filterOriginalBuilds(builds), nil
}

func filterOriginalBuilds(builds []*bb.Build) []*bb.Build {
	filtered := make([]*bb.Build, 0, len(builds))
	for _, b := range builds {
		if isOriginalBuild(b) {
			filtered = append(filtered, b)
		}
	}
	return filtered
}

func isOriginalBuild(b *bb.Build) bool {
	return !isBackfillBuild(b)
}

// getLatestBackfillBuildFor returns nil (and no error) if no backfill build is
// found.
func (c *backfillRequestRun) getLatestBackfillBuildFor(ctx context.Context, b *bb.Build) (*bb.Build, error) {
	builds, err := c.bbClient.SearchBuildsByTags(ctx, bbBuildSearchLimit, backfillTags(b.Tags, b.ID)...)
	if err != nil {
		return nil, errors.Annotate(err, "get latest backfill build for %d", b.ID).Err()
	}
	if len(builds) == 0 {
		return nil, nil
	}
	// buildbucket builds IDs are monotonically decreasing.
	// The build with the smallest ID is the latest.
	sort.Slice(builds, func(i, j int) bool {
		return builds[i].ID < builds[j].ID
	})
	return builds[0], nil
}

func (c *backfillRequestRun) confirmMultileBuildsOK(a subcommands.Application, builds []*bb.Build) bool {
	prompt := userinput.CLIPrompt(a.GetOut(), os.Stdin, false)
	return prompt(fmt.Sprintf("Found %d builds to backfill. Create requests for them all [y/N]? ", len(builds)))
}

func (c *backfillRequestRun) scheduleBackfillBuild(ctx context.Context, original *bb.Build) (int64, error) {
	var req *structpb.Struct
	switch {
	case original.RawBackfillRequest != nil:
		req = original.RawBackfillRequest
	case original.RawRequest != nil:
		logging.Infof(ctx, "Original build %d has no backfill_request. Using original request instead.", original.ID)
		req = original.RawRequest
	default:
		return -1, errors.Reason("schedule backfill: build %d has no request to clone", original.ID).Err()
	}

	ID, err := c.bbClient.ScheduleBuildRaw(ctx, req, backfillTags(original.Tags, original.ID))
	if err != nil {
		return -1, errors.Annotate(err, "schedule backfill").Err()
	}
	return ID, nil
}

func backfillTags(tags []string, originalID int64) []string {
	ntags := make([]string, 0, len(tags))
	for _, t := range tags {
		if isSkylabToolTag(t) {
			continue
		}
		ntags = append(ntags, t)
	}
	return append(ntags, "skylab-tool:backfill-request", fmt.Sprintf("backfill:%d", originalID))
}

func isSkylabToolTag(t string) bool {
	return strings.HasPrefix(t, "skylab-tool:")
}
