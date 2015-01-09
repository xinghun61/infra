// Copyright 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

/*
Client side of for Chrome Infra Package Deployer.

TODO: write more.

Subcommand starting with 'pkg-' are low level commands operating on package
files on disk.
*/
package main

import (
	"flag"
	"fmt"
	"net/http"
	"os"
	"strings"

	"infra/libs/auth"
	"infra/libs/logging"

	"infra/tools/cipd"

	"github.com/maruel/subcommands"
)

////////////////////////////////////////////////////////////////////////////////
// Utility functions.

// reportError writes a error message to stderr and log file.
func reportError(format string, params ...interface{}) {
	msg := fmt.Sprintf(format, params...)
	logging.Errorf("%s", msg)
	if !logging.IsTerminal {
		fmt.Fprintf(os.Stderr, msg+"\n")
	}
}

// checkCommandLine ensures all required positional and flag-like parameters
// are set. Returns true if they are, or false (and prints to stderr) if not.
func checkCommandLine(args []string, flags *flag.FlagSet, positionalCount int) bool {
	// Check number of expected positional arguments.
	if positionalCount == 0 && len(args) != 0 {
		reportError("Unexpected arguments: %v", args)
		return false
	}
	if len(args) != positionalCount {
		reportError("Expecting %d arguments, got %d", positionalCount, len(args))
		return false
	}
	// Check required unset flags.
	unset := []*flag.Flag{}
	flags.VisitAll(func(f *flag.Flag) {
		if strings.HasPrefix(f.DefValue, "<") && f.Value.String() == f.DefValue {
			unset = append(unset, f)
		}
	})
	if len(unset) != 0 {
		missing := []string{}
		for _, f := range unset {
			missing = append(missing, f.Name)
		}
		reportError("Missing required flags: %v", missing)
		return false
	}
	return true
}

////////////////////////////////////////////////////////////////////////////////
// 'build' subcommand.

var cmdBuild = &subcommands.Command{
	UsageLine: "pkg-build [options]",
	ShortDesc: "builds a package instance file",
	LongDesc:  "Builds a package instance producing *.cipd file.",
	CommandRun: func() subcommands.CommandRun {
		c := &buildRun{}
		c.Flags.StringVar(&c.packageName, "name", "<name>", "package name")
		c.Flags.StringVar(&c.inputDir, "in", "<path>", "path to a directory with files to package")
		c.Flags.StringVar(&c.outputFile, "out", "<path>", "path to a file to write the final package to")
		return c
	},
}

type buildRun struct {
	subcommands.CommandRunBase
	packageName string
	inputDir    string
	outputFile  string
}

func (c *buildRun) Run(a subcommands.Application, args []string) int {
	if !checkCommandLine(args, c.GetFlags(), 0) {
		return 1
	}
	err := buildInstanceFile(c.packageName, c.inputDir, c.outputFile)
	if err != nil {
		reportError("Error while building the package: %s", err)
		return 1
	}
	return 0
}

func buildInstanceFile(packageName string, inputDir string, instanceFile string) error {
	// Read the list of files to add to the package.
	files, err := cipd.ScanFileSystem(inputDir)
	if err != nil {
		return err
	}

	// Build the package.
	out, err := os.OpenFile(instanceFile, os.O_RDWR|os.O_CREATE|os.O_TRUNC, 0666)
	if err != nil {
		return err
	}
	err = cipd.BuildInstance(cipd.BuildInstanceOptions{
		Input:       files,
		Output:      out,
		PackageName: packageName,
	})
	out.Close()
	if err != nil {
		os.Remove(instanceFile)
		return err
	}

	// Print information about built package, also verify it is readable.
	return inspectInstanceFile(instanceFile, false)
}

////////////////////////////////////////////////////////////////////////////////
// 'deploy' subcommand.

var cmdDeploy = &subcommands.Command{
	UsageLine: "pkg-deploy [options] <package instance file>",
	ShortDesc: "deploys a package instance file",
	LongDesc:  "Deploys a *.cipd package instance into a site root.",
	CommandRun: func() subcommands.CommandRun {
		c := &deployRun{}
		c.Flags.StringVar(&c.rootDir, "root", "<path>", "path to a installation site root directory")
		return c
	},
}

type deployRun struct {
	subcommands.CommandRunBase

	rootDir string
}

func (c *deployRun) Run(a subcommands.Application, args []string) int {
	if !checkCommandLine(args, c.GetFlags(), 1) {
		return 1
	}
	err := deployInstanceFile(c.rootDir, args[0])
	if err != nil {
		reportError("Error while deploying the package: %s", err)
		return 1
	}
	return 0
}

func deployInstanceFile(root string, instanceFile string) error {
	inst, err := cipd.OpenInstanceFile(instanceFile, "")
	if err != nil {
		return err
	}
	defer inst.Close()
	inspectInstance(inst, false)
	_, err = cipd.DeployInstance(root, inst)
	return err
}

////////////////////////////////////////////////////////////////////////////////
// 'fetch' subcommand.

var cmdFetch = &subcommands.Command{
	UsageLine: "pkg-fetch [options]",
	ShortDesc: "fetches a package instance file from the repository",
	LongDesc:  "Fetches a package instance file from the repository.",
	CommandRun: func() subcommands.CommandRun {
		c := &fetchRun{}
		c.Flags.StringVar(&c.packageName, "name", "<name>", "package name")
		c.Flags.StringVar(&c.instanceID, "instance-id", "<instance id>", "package instance ID to fetch")
		c.Flags.StringVar(&c.outputPath, "out", "<path>", "path to a file to write fetch to")
		return c
	},
}

type fetchRun struct {
	subcommands.CommandRunBase

	packageName string
	instanceID  string
	outputPath  string
}

func (c *fetchRun) Run(a subcommands.Application, args []string) int {
	if !checkCommandLine(args, c.GetFlags(), 0) {
		return 1
	}
	client, err := auth.AuthenticatedClient(false, nil)
	if err != nil {
		reportError("Error when authenticating: %s", err)
		return 1
	}
	err = fetchInstanceFile(c.packageName, c.instanceID, c.outputPath, client)
	if err != nil {
		reportError("Error while fetching the package: %s", err)
		return 1
	}
	return 0
}

func fetchInstanceFile(packageName, instanceID, instanceFile string, client *http.Client) error {
	// Fetch it.
	out, err := os.OpenFile(instanceFile, os.O_CREATE|os.O_WRONLY, 0666)
	if err != nil {
		return err
	}
	ok := false
	defer func() {
		if !ok {
			out.Close()
			os.Remove(instanceFile)
		}
	}()

	err = cipd.FetchInstance(cipd.FetchInstanceOptions{
		Client:      client,
		PackageName: packageName,
		InstanceID:  instanceID,
		Output:      out,
	})
	if err != nil {
		return err
	}

	// Verify it (by checking that instanceID matches the file content).
	out.Close()
	ok = true
	inst, err := cipd.OpenInstanceFile(instanceFile, instanceID)
	if err != nil {
		os.Remove(instanceFile)
		return err
	}
	defer inst.Close()
	inspectInstance(inst, false)
	return nil
}

////////////////////////////////////////////////////////////////////////////////
// 'inspect' subcommand.

var cmdInspect = &subcommands.Command{
	UsageLine: "pkg-inspect <package instance file>",
	ShortDesc: "inspects contents of a package instance file",
	LongDesc:  "Reads contents *.cipd file and prints information about it.",
	CommandRun: func() subcommands.CommandRun {
		return &inspectRun{}
	},
}

type inspectRun struct {
	subcommands.CommandRunBase
}

func (c *inspectRun) Run(a subcommands.Application, args []string) int {
	if !checkCommandLine(args, c.GetFlags(), 1) {
		return 1
	}
	err := inspectInstanceFile(args[0], true)
	if err != nil {
		reportError("Error while inspecting the package: %s", err)
		return 1
	}
	return 0
}

func inspectInstanceFile(instanceFile string, listFiles bool) error {
	inst, err := cipd.OpenInstanceFile(instanceFile, "")
	if err != nil {
		return err
	}
	defer inst.Close()
	inspectInstance(inst, listFiles)
	return nil
}

func inspectInstance(inst cipd.PackageInstance, listFiles bool) {
	logging.Infof("Package name: %s", inst.PackageName())
	logging.Infof("Instance ID:  %s", inst.InstanceID())
	if listFiles {
		logging.Infof("Package files:")
		for _, f := range inst.Files() {
			logging.Infof("  %v", f.Name())
		}
	}
}

////////////////////////////////////////////////////////////////////////////////
// 'register' subcommand.

var cmdRegister = &subcommands.Command{
	UsageLine: "pkg-register <package instance file>",
	ShortDesc: "uploads and registers package instance in the package repository",
	LongDesc:  "Uploads and registers package instance in the package repository.",
	CommandRun: func() subcommands.CommandRun {
		return &registerRun{}
	},
}

type registerRun struct {
	subcommands.CommandRunBase
}

func (c *registerRun) Run(a subcommands.Application, args []string) int {
	if !checkCommandLine(args, c.GetFlags(), 1) {
		return 1
	}
	client, err := auth.AuthenticatedClient(true, nil)
	if err != nil {
		reportError("Error when authenticating: %s", err)
		return 1
	}
	err = registerInstanceFile(args[0], client)
	if err != nil {
		reportError("Error while registering the package: %s", err)
		return 1
	}
	return 0
}

func registerInstanceFile(instanceFile string, client *http.Client) error {
	inst, err := cipd.OpenInstanceFile(instanceFile, "")
	if err != nil {
		return err
	}
	defer inst.Close()
	logging.Infof("Registering package %s:%s", inst.PackageName(), inst.InstanceID())
	inspectInstance(inst, false)
	return cipd.RegisterInstance(cipd.RegisterInstanceOptions{
		PackageInstance: inst,
		UploadOptions: cipd.UploadOptions{
			Client: client,
		},
	})
}

////////////////////////////////////////////////////////////////////////////////
// 'upload' subcommand.

var cmdUpload = &subcommands.Command{
	UsageLine: "pkg-upload <package instance file>",
	ShortDesc: "uploads package data blob to the CAS store",
	LongDesc:  "Uploads package data blob to the CAS store.",
	CommandRun: func() subcommands.CommandRun {
		return &uploadRun{}
	},
}

type uploadRun struct {
	subcommands.CommandRunBase
}

func (c *uploadRun) Run(a subcommands.Application, args []string) int {
	if !checkCommandLine(args, c.GetFlags(), 1) {
		return 1
	}
	client, err := auth.AuthenticatedClient(true, nil)
	if err != nil {
		reportError("Error when authenticating: %s", err)
		return 1
	}
	err = uploadInstanceFile(args[0], client)
	if err != nil {
		reportError("Error while uploading the package: %s", err)
		return 1
	}
	return 0
}

func uploadInstanceFile(instanceFile string, client *http.Client) error {
	inst, err := cipd.OpenInstanceFile(instanceFile, "")
	if err != nil {
		return err
	}
	defer inst.Close()
	logging.Infof("Uploading package instance %s", inst.InstanceID())
	inspectInstance(inst, false)
	return cipd.UploadToCAS(cipd.UploadToCASOptions{
		SHA1: inst.InstanceID(),
		Data: inst.DataReader(),
		UploadOptions: cipd.UploadOptions{
			Client: client,
		},
	})
}

////////////////////////////////////////////////////////////////////////////////
// Main.

var application = &subcommands.DefaultApplication{
	Name:  "cipd",
	Title: "Chrome infra package deployer.",
	Commands: []*subcommands.Command{
		subcommands.CmdHelp,

		cmdBuild,
		cmdDeploy,
		cmdFetch,
		cmdInspect,
		cmdRegister,
		cmdUpload,
	},
}

func main() {
	os.Exit(subcommands.Run(application, nil))
}
