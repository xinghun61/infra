// Copyright 2017 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package main

import (
	"encoding/json"
	"fmt"
	"os"
	"strings"

	"golang.org/x/net/context"

	"github.com/maruel/subcommands"

	"go.chromium.org/luci/client/authcli"
	swarmbucket "go.chromium.org/luci/common/api/buildbucket/swarmbucket/v1"
	swarming "go.chromium.org/luci/common/api/swarming/swarming/v1"
	"go.chromium.org/luci/common/auth"
	"go.chromium.org/luci/common/cli"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/common/retry/transient"
)

const bbHostDefault = "cr-buildbucket.appspot.com"

func getBuilderCmd(authOpts auth.Options) *subcommands.Command {
	return &subcommands.Command{
		UsageLine: "get-builder bucket_name:builder_name",
		ShortDesc: "obtain a JobDefinition from a buildbucket builder",
		LongDesc:  `Obtains the builder definition from buildbucket and produces a JobDefinition.`,

		CommandRun: func() subcommands.CommandRun {
			ret := &cmdGetBuilder{}
			ret.logCfg.Level = logging.Info

			ret.logCfg.AddFlags(&ret.Flags)
			ret.authFlags.Register(&ret.Flags, authOpts)

			ret.Flags.StringVar(&ret.bbHost, "B", bbHostDefault,
				"The buildbucket hostname to grab the definition from.")

			return ret
		},
	}
}

type cmdGetBuilder struct {
	subcommands.CommandRunBase

	logCfg    logging.Config
	authFlags authcli.Flags

	bbHost string
}

func (c *cmdGetBuilder) validateFlags(ctx context.Context, args []string) (authOpts auth.Options, bucket, builder string, err error) {
	if len(args) != 1 {
		err = errors.Reason("unexpected positional arguments: %q", args).Err()
		return
	}
	if err = validateHost(c.bbHost); err != nil {
		err = errors.Annotate(err, "").Err()
		return
	}

	toks := strings.SplitN(args[0], ":", 2)
	if len(toks) != 2 {
		err = errors.Reason("cannot parse bucket:builder: %q", args[0]).Err()
		return
	}
	bucket, builder = toks[0], toks[1]
	if bucket == "" {
		err = errors.New("empty bucket")
		return
	}
	if builder == "" {
		err = errors.New("empty builder")
		return
	}
	authOpts, err = c.authFlags.Options()
	return
}

func (c *cmdGetBuilder) grabBuilderDefinition(ctx context.Context, bucket, builder string, authOpts auth.Options) (*JobDefinition, error) {
	authenticator := auth.NewAuthenticator(ctx, auth.SilentLogin, authOpts)
	authClient, err := authenticator.Client()
	if err != nil {
		return nil, err
	}
	sbucket, err := swarmbucket.New(authClient)
	sbucket.BasePath = fmt.Sprintf("https://%s/api/swarmbucket/v1/", c.bbHost)

	type parameters struct {
		BuilderName     string `json:"builder_name"`
		APIExplorerLink bool   `json:"api_explorer_link"`
	}

	data, err := json.Marshal(&parameters{builder, false})
	if err != nil {
		return nil, err
	}

	args := &swarmbucket.SwarmingSwarmbucketApiGetTaskDefinitionRequestMessage{
		BuildRequest: &swarmbucket.ApiPutRequestMessage{
			Bucket:         bucket,
			ParametersJson: string(data),
		},
	}
	answer, err := sbucket.GetTaskDef(args).Context(ctx).Do()
	if err != nil {
		return nil, transient.Tag.Apply(err)
	}

	newTask := &swarming.SwarmingRpcsNewTaskRequest{}
	r := strings.NewReader(answer.TaskDefinition)
	if err := json.NewDecoder(r).Decode(newTask); err != nil {
		return nil, err
	}

	jd, err := JobDefinitionFromNewTaskRequest(newTask)
	if err != nil {
		return nil, err
	}
	// TODO(iannucci): obtain swarming server from answer
	jd.SwarmingHostname = "chromium-swarm.appspot.com"
	if strings.Contains(c.bbHost, "-dev.") {
		jd.SwarmingHostname = "chromium-swarm-dev.appspot.com"
	}

	return jd, nil
}

func (c *cmdGetBuilder) Run(a subcommands.Application, args []string, env subcommands.Env) int {
	ctx := c.logCfg.Set(cli.GetContext(a, c, env))
	authOpts, bucket, builder, err := c.validateFlags(ctx, args)
	if err != nil {
		logging.Errorf(ctx, "bad arguments: %s\n\n", err)
		c.GetFlags().Usage()
		return 1
	}

	logging.Infof(ctx, "getting builder definition")
	jd, err := c.grabBuilderDefinition(ctx, bucket, builder, authOpts)
	if err != nil {
		errors.Log(ctx, err)
		return 1
	}
	logging.Infof(ctx, "getting builder definition: done")

	enc := json.NewEncoder(os.Stdout)
	enc.SetIndent("", "  ")
	if err := enc.Encode(jd); err != nil {
		errors.Log(ctx, err)
		return 1
	}

	return 0
}
