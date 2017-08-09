// Copyright 2017 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"net/http"
	"os"
	"strconv"
	"strings"

	"go.chromium.org/luci/client/authcli"
	"go.chromium.org/luci/common/api/buildbucket/buildbucket/v1"
	"go.chromium.org/luci/common/auth"
	"go.chromium.org/luci/common/cli"
	"go.chromium.org/luci/common/data/rand/mathrand"
	"go.chromium.org/luci/common/errors"
	log "go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/common/logging/gologger"
	miloProto "go.chromium.org/luci/common/proto/milo"
	"go.chromium.org/luci/common/sync/parallel"
	"go.chromium.org/luci/grpc/prpc"
	milo "go.chromium.org/luci/milo/api/proto"

	"github.com/golang/protobuf/proto"
	"github.com/maruel/subcommands"
	"golang.org/x/net/context"

	"go.chromium.org/luci/hardcoded/chromeinfra"
)

////////////////////////////////////////////////////////////////////////////////
// main
////////////////////////////////////////////////////////////////////////////////

type application struct {
	cli.Application

	authOpts auth.Options

	miloHost string
}

func getApplication(base subcommands.Application) (*application, context.Context) {
	app := base.(*application)
	return app, app.Context(context.Background())
}

func (app *application) addFlags(fs *flag.FlagSet) {
	fs.StringVar(&app.miloHost, "milo-host", "luci-milo.appspot.com", "Milo host.")
}

func (app *application) getClient(c context.Context) (*http.Client, error) {
	a := auth.NewAuthenticator(c, auth.SilentLogin, app.authOpts)
	authClient, err := a.Client()
	if err != nil {
		return nil, errors.Annotate(err, "failed to get authenticating client").Err()
	}
	return authClient, nil
}

func mainImpl(c context.Context, defaultAuthOpts auth.Options, args []string) int {
	c = gologger.StdConfig.Use(c)

	logConfig := log.Config{
		Level: log.Warning,
	}

	var authFlags authcli.Flags

	app := application{
		Application: cli.Application{
			Name:  "Build Comparison Utility",
			Title: "Build Comparison Utility",
			Context: func(c context.Context) context.Context {
				// Install configured logger.
				c = logConfig.Set(gologger.StdConfig.Use(c))
				return c
			},

			Commands: []*subcommands.Command{
				subcommands.CmdHelp,

				&subcommandCompare,

				authcli.SubcommandLogin(defaultAuthOpts, "auth-login", false),
				authcli.SubcommandLogout(defaultAuthOpts, "auth-logout", false),
				authcli.SubcommandInfo(defaultAuthOpts, "auth-info", false),
			},
		},
	}

	fs := flag.NewFlagSet("flags", flag.ExitOnError)
	app.addFlags(fs)
	logConfig.AddFlags(fs)
	authFlags.Register(fs, defaultAuthOpts)
	fs.Parse(args)

	// Process authentication options.
	var err error
	app.authOpts, err = authFlags.Options()
	if err != nil {
		log.WithError(err).Errorf(c, "Failed to create auth options.")
		return 1
	}

	// Execute our subcommand.
	return subcommands.Run(&app, fs.Args())
}

func main() {
	mathrand.SeedRandomly()
	os.Exit(mainImpl(context.Background(), chromeinfra.DefaultAuthOptions(), os.Args[1:]))
}

func renderErr(c context.Context, err error) {
	log.Errorf(c, "Error encountered during operation: %s\n%s", err,
		strings.Join(errors.RenderStack(err), "\n"))
}

////////////////////////////////////////////////////////////////////////////////
// Subcommand: get
////////////////////////////////////////////////////////////////////////////////

type cmdRunCompare struct {
	subcommands.CommandRunBase

	swHost string
	bbHost string
	task   string
}

var subcommandCompare = subcommands.Command{
	UsageLine: "compare [options] <task...>",
	ShortDesc: "Compares a SwarmBucket build to its BuildBot equivalent.",
	CommandRun: func() subcommands.CommandRun {
		var cmd cmdRunCompare

		fs := cmd.GetFlags()
		fs.StringVar(&cmd.swHost, "swarming-host", "chromium-swarm.appspot.com", "Swarming host (required).")
		fs.StringVar(&cmd.bbHost, "buildbucket-host", "cr-buildbucket.appspot.com", "BuildBucket host (required).")

		return &cmd
	},
}

func (cmd *cmdRunCompare) Run(baseApp subcommands.Application, args []string, _ subcommands.Env) int {
	app, c := getApplication(baseApp)

	switch {
	case cmd.swHost == "":
		log.Errorf(c, "Missing required argument (-swarming-host).")
		return 1

	case cmd.bbHost == "":
		log.Errorf(c, "Missing required argument (-buildbucket-host).")
		return 1
	}

	authClient, err := app.getClient(c)
	if err != nil {
		renderErr(c, err)
		return 1
	}

	miloClient := milo.NewBuildInfoPRPCClient(&prpc.Client{
		C:    authClient,
		Host: app.miloHost,
	})

	bbClient, err := buildbucket.New(authClient)
	if err != nil {
		renderErr(c, errors.Annotate(err, "failed to create BuildBucket client").Err())
		return 1
	}
	bbClient.BasePath = fmt.Sprintf("https://%s/api/buildbucket/v1/", cmd.bbHost)

	var rb reportBuilder
	err = parallel.FanOutIn(func(workC chan<- func() error) {
		for _, task := range args {
			task := task
			workC <- func() error {
				cr, err := cmd.compareBuilds(c, task, miloClient, bbClient)
				if err != nil {
					return errors.Annotate(err, "failed to compare builds for %q", task).Err()
				}
				rb.addTask(task, cr)
				return nil
			}
		}
	})
	if err != nil {
		renderErr(c, errors.Annotate(err, "failed to compare builds").Err())
		return 1
	}

	report := rb.generateReport()
	report.log(c)
	return 0
}

func (cmd *cmdRunCompare) compareBuilds(c context.Context, task string, miloClient milo.BuildInfoClient, bbClient *buildbucket.Service) (
	*compareResult, error) {

	// Fetch the Swarming build info.
	sbInfo, err := miloClient.Get(c, &milo.BuildInfoRequest{
		Build: &milo.BuildInfoRequest_Swarming_{
			Swarming: &milo.BuildInfoRequest_Swarming{
				Host: cmd.swHost,
				Task: task,
			},
		},
	})
	if err != nil {
		return nil, errors.Annotate(err, "failed to get Swarming task %q", task).Err()
	}

	if log.IsLogging(c, log.Info) {
		log.Infof(c, "Got Swarming build:\n%s", proto.MarshalTextString(sbInfo))
	}

	// We need to load the BuildBot build's BuildBucket information in order to
	// identify its actual build number. The build number in the SwarmBucket task
	// is assigned independently.
	buildBucketID, err := getBuildBucketID(sbInfo.Step)
	if err != nil {
		return nil, err
	}
	log.Infof(c, "Got BuildBot build's BuildBuket ID: %v", buildBucketID)

	bbResp, err := bbClient.Get(buildBucketID).Context(c).Do()
	if err != nil {
		return nil, errors.Annotate(err, "failed to get BuildBucket ID %v", buildBucketID).Err()
	}
	log.Infof(c, "Got details JSON from BuildBucket response: %#v", bbResp.Build.ResultDetailsJson)

	var bbParams struct {
		Properties struct {
			MasterName  string `json:"mastername"`
			BuilderName string `json:"buildername"`
			BuildNumber int64  `json:"buildnumber"`
		}
	}
	if err := json.Unmarshal([]byte(bbResp.Build.ResultDetailsJson), &bbParams); err != nil {
		return nil, errors.Annotate(err, "failed to unmarshal result details JSON").Err()
	}

	switch {
	case bbParams.Properties.MasterName == "":
		return nil, errors.New("invalid mastername property")
	case bbParams.Properties.BuilderName == "":
		return nil, errors.New("invalid buildername property")
	}

	log.Infof(c, "Identified BuildBot build as mastername=%q, buildername=%q, buildnumber=%v",
		bbParams.Properties.MasterName, bbParams.Properties.BuilderName, bbParams.Properties.BuildNumber)

	// Extract the BuildBot task from it.
	bbInfo, err := miloClient.Get(c, &milo.BuildInfoRequest{
		Build: &milo.BuildInfoRequest_Buildbot{
			Buildbot: &milo.BuildInfoRequest_BuildBot{
				MasterName:  bbParams.Properties.MasterName,
				BuilderName: bbParams.Properties.BuilderName,
				BuildNumber: bbParams.Properties.BuildNumber,
			},
		},
	})
	if err != nil {
		return nil, errors.Annotate(err, "failed to get BuildBot task %v.%v.%v",
			bbParams.Properties.MasterName, bbParams.Properties.BuilderName, bbParams.Properties.BuildNumber).Err()
	}

	if log.IsLogging(c, log.Info) {
		log.Infof(c, "Got BuildBucket build:\n%s", proto.MarshalTextString(bbInfo))
	}

	return compare(bbInfo.Step, sbInfo.Step), nil
}

func getPropertyValue(s *miloProto.Step, k string) (string, bool) {
	if s == nil {
		return "", false
	}
	for _, prop := range s.Property {
		if prop.Name == k {
			return prop.Value, true
		}
	}
	for _, subStep := range s.Substep {
		if v, ok := getPropertyValue(subStep.GetStep(), k); ok {
			return v, true
		}
	}
	return "", false
}

func getBuildBucketID(s *miloProto.Step) (int64, error) {
	v, ok := getPropertyValue(s, "buildbucket")
	if !ok {
		return 0, errors.New("no buildbucket property")
	}

	var buildBucketProp struct {
		Build struct {
			Tags []string
		}
	}
	if err := json.Unmarshal([]byte(v), &buildBucketProp); err != nil {
		return 0, errors.Annotate(err, "failed to unmarshal buildbucket property").Err()
	}

	var migrationTag string
	for _, tag := range buildBucketProp.Build.Tags {
		parts := strings.SplitN(tag, ":", 2)
		if len(parts) != 2 || parts[0] != "luci_migration_buildbot_build_id" {
			continue
		}
		migrationTag = parts[1]
		break
	}
	if migrationTag == "" {
		return 0, errors.Reason("failed to extract migration build ID").Err()
	}

	id, err := strconv.ParseInt(migrationTag, 10, 64)
	if err != nil {
		return 0, errors.Annotate(err, "failed to parse migration ID %q", migrationTag).Err()
	}
	return id, nil
}
