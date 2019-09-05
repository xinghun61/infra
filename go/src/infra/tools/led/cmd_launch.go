// Copyright 2017 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package main

import (
	"encoding/hex"
	"encoding/json"
	"os"
	"time"

	"golang.org/x/net/context"

	"github.com/maruel/subcommands"

	"go.chromium.org/luci/auth"
	"go.chromium.org/luci/auth/client/authcli"
	"go.chromium.org/luci/common/cli"
	"go.chromium.org/luci/common/data/rand/cryptorand"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/gcloud/googleoauth"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/common/system/terminal"
	logdog_types "go.chromium.org/luci/logdog/common/types"
)

func launchCmd(authOpts auth.Options) *subcommands.Command {
	return &subcommands.Command{
		UsageLine: "launch",
		ShortDesc: "launches a JobDefinition on swarming",
		LongDesc: `Launches a given JobDefinition on swarming.

Example:

led get-builder ... |
  led edit ... |
  led launch

If stdout is not a tty (e.g. a file), this command writes a JSON object
containing information about the launched task to stdout.
`,

		CommandRun: func() subcommands.CommandRun {
			ret := &cmdLaunch{}
			ret.logCfg.Level = logging.Info

			ret.logCfg.AddFlags(&ret.Flags)
			ret.authFlags.Register(&ret.Flags, authOpts)

			ret.Flags.BoolVar(&ret.dump, "dump", false, "Dump swarming task to stdout instead of running it.")

			return ret
		},
	}
}

type cmdLaunch struct {
	subcommands.CommandRunBase

	logCfg    logging.Config
	authFlags authcli.Flags

	dump bool
}

func (c *cmdLaunch) validateFlags(ctx context.Context, args []string) (authOpts auth.Options, err error) {
	if len(args) > 0 {
		err = errors.Reason("unexpected positional arguments: %q", args).Err()
		return
	}
	return c.authFlags.Options()
}

type launchedTaskInfo struct {
	Swarming struct {
		// The swarming task ID of the launched task.
		TaskID string `json:"task_id"`

		// The hostname of the swarming server
		Hostname string `json:"host_name"`
	} `json:"swarming"`
}

// setOutputResultPath tells the task to write its result to a JSON file in the ISOLATED_OUTDIR.
// This is an interface for getting structured output from a task launched by led.
func setOutputResultPath(s *Systemland) error {
	ka := s.KitchenArgs
	if ka == nil {
		// TODO(iannucci): Support LUCI runner.
		// Intentionally not fatal. led supports jobs which don't use kitchen or LUCI runner,
		// and we don't want to block that usage.
		return nil
	}
	ka.OutputResultJSONPath = "${ISOLATED_OUTDIR}/build.proto.json"
	return nil
}

// setInputRecipes passes the CIPD package or isolate containing the recipes
// code into the led recipe module. This gives the build the information it
// needs to launch child builds using the same version of the recipes code.

func generateLogdogPrefix(ctx context.Context, uid string) (prefix logdog_types.StreamName, err error) {
	buf := make([]byte, 32)
	if _, err := cryptorand.Read(ctx, buf); err != nil {
		return "", errors.Annotate(err, "generating random token").Err()
	}
	return logdog_types.MakeStreamName("", "led", uid, hex.EncodeToString(buf))
}

func (c *cmdLaunch) Run(a subcommands.Application, args []string, env subcommands.Env) int {
	ctx := c.logCfg.Set(cli.GetContext(a, c, env))
	authOpts, err := c.validateFlags(ctx, args)
	if err != nil {
		logging.Errorf(ctx, "bad arguments: %s\n\n", err)
		c.GetFlags().Usage()
		return 1
	}

	jd, err := decodeJobDefinition(ctx)
	if err != nil {
		errors.Log(ctx, err)
		return 1
	}

	authClient, swarm, err := newSwarmClient(ctx, authOpts, jd.SwarmingHostname)
	if err != nil {
		errors.Log(ctx, err)
		return 1
	}

	authenticator := auth.NewAuthenticator(ctx, auth.SilentLogin, authOpts)
	tok, err := authenticator.GetAccessToken(time.Minute)
	if err != nil {
		logging.WithError(err).Errorf(ctx, "getting access token")
		return 1
	}
	info, err := googleoauth.GetTokenInfo(ctx, googleoauth.TokenInfoParams{
		AccessToken: tok.AccessToken,
	})
	uid := info.Email
	if uid == "" {
		uid = "uid:" + info.Sub
	}

	isoFlags, err := getIsolatedFlags(swarm)
	if err != nil {
		errors.Log(ctx, err)
		return 1
	}

	isoClient, err := newIsolatedClient(ctx, isoFlags, authClient)
	if err != nil {
		errors.Log(ctx, err)
		return 1
	}

	logdogPrefix, err := generateLogdogPrefix(ctx, uid)
	if err != nil {
		errors.Log(ctx, err)
		return 1
	}

	ejd := jd.Edit()
	ejd.tweakSystemland(setOutputResultPath)
	ejd.ConsolidateIsolateSources(ctx, isoClient)
	// Set the "$recipe_engine/led" recipe properties.
	ejd.tweakUserland(func(u *Userland) error {
		ledProperties := map[string]interface{}{
			"launched_by_led": true,
			"led_run_id":      logdogPrefix,
		}
		// Pass the CIPD package or isolate containing the recipes code into
		// the led recipe module. This gives the build the information it needs
		// to launch child builds using the same version of the recipes code.
		if u.RecipeIsolatedHash != "" {
			ledProperties["isolated_input"] = map[string]interface{}{
				// TODO(iannucci): Set server and namespace too.
				"hash": u.RecipeIsolatedHash,
			}
		} else if u.RecipeCIPDSource != nil {
			ledProperties["cipd_input"] = map[string]interface{}{
				"package": u.RecipeCIPDSource.Package,
				"version": u.RecipeCIPDSource.Version,
			}
		}
		u.RecipeProperties["$recipe_engine/led"] = ledProperties
		return nil
	})
	if err := ejd.Finalize(); err != nil {
		errors.Log(ctx, err)
		return 1
	}

	jd.TopLevel.Tags = append(jd.TopLevel.Tags, "user:"+uid)

	logging.Infof(ctx, "building swarming task")
	st, err := jd.GetSwarmingNewTask(ctx, uid, logdogPrefix)
	if err != nil {
		errors.Log(ctx, err)
		return 1
	}
	logging.Infof(ctx, "building swarming task: done")

	if c.dump {
		if err = json.NewEncoder(os.Stdout).Encode(st); err != nil {
			errors.Log(ctx, err)
			return 1
		}
		return 0
	}

	logging.Infof(ctx, "launching swarming task")
	req, err := swarm.Tasks.New(st).Do()
	if err != nil {
		errors.Log(ctx, err)
		return 1
	}
	logging.Infof(ctx, "launching swarming task: done")

	logging.Infof(ctx, "Launched swarming task: https://%s/task?id=%s",
		jd.SwarmingHostname, req.TaskId)
	logging.Infof(ctx, "LUCI UI: https://ci.chromium.org/swarming/task/%s?server=%s",
		req.TaskId, jd.SwarmingHostname)

	if !terminal.IsTerminal(int(os.Stdout.Fd())) {
		lti := launchedTaskInfo{}
		lti.Swarming.TaskID = req.TaskId
		lti.Swarming.Hostname = jd.SwarmingHostname
		if err = json.NewEncoder(os.Stdout).Encode(lti); err != nil {
			errors.Log(ctx, err)
			return 1
		}
	}

	return 0
}
