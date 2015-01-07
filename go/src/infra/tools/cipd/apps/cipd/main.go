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

// authenticatedClient performs login and returns http.Client.
func authenticatedClient() (*http.Client, error) {
	logging.Infof("Authenticating...")
	transport, err := auth.LoginIfRequired(nil)
	if err != nil {
		return nil, err
	}
	ident, err := auth.FetchIdentity(transport)
	if err != nil {
		return nil, err
	}
	logging.Infof("Authenticated as %s", ident)
	return &http.Client{Transport: transport}, nil
}

////////////////////////////////////////////////////////////////////////////////
// 'build' subcommand.

var cmdBuild = &subcommands.Command{
	UsageLine: "pkg-build [options]",
	ShortDesc: "builds a package file",
	LongDesc:  "Builds a package producing *.cipd file.",
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
	err := buildPackageFile(c.packageName, c.inputDir, c.outputFile)
	if err != nil {
		reportError("Error while building the package: %s", err)
		return 1
	}
	return 0
}

func buildPackageFile(packageName string, inputDir string, packageFile string) error {
	// Read the list of files to add to the package.
	files, err := cipd.ScanFileSystem(inputDir)
	if err != nil {
		return err
	}

	// Build the package.
	out, err := os.OpenFile(packageFile, os.O_RDWR|os.O_CREATE|os.O_TRUNC, 0666)
	if err != nil {
		return err
	}
	err = cipd.BuildPackage(cipd.BuildPackageOptions{
		Input:       files,
		Output:      out,
		PackageName: packageName,
	})
	out.Close()
	if err != nil {
		os.Remove(packageFile)
		return err
	}

	// Print information about built package, also verify it is readable.
	return inspectPackageFile(packageFile, false)
}

////////////////////////////////////////////////////////////////////////////////
// 'deploy' subcommand.

var cmdDeploy = &subcommands.Command{
	UsageLine: "pkg-deploy [options] <package file>",
	ShortDesc: "deploys a package file",
	LongDesc:  "Deploys a *.cipd package into a site root.",
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
	err := deployPackageFile(c.rootDir, args[0])
	if err != nil {
		reportError("Error while deploying the package: %s", err)
		return 1
	}
	return 0
}

func deployPackageFile(root string, packageFile string) error {
	pkg, err := cipd.OpenPackageFile(packageFile, "")
	if err != nil {
		return err
	}
	defer pkg.Close()
	inspectPackage(pkg, false)
	_, err = cipd.Deploy(root, pkg)
	return err
}

////////////////////////////////////////////////////////////////////////////////
// 'inspect' subcommand.

var cmdInspect = &subcommands.Command{
	UsageLine: "pkg-inspect <package file>",
	ShortDesc: "inspects contents of a package file",
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
	err := inspectPackageFile(args[0], true)
	if err != nil {
		reportError("Error while inspecting the package: %s", err)
		return 1
	}
	return 0
}

func inspectPackageFile(packageFile string, listFiles bool) error {
	pkg, err := cipd.OpenPackageFile(packageFile, "")
	if err != nil {
		return err
	}
	defer pkg.Close()
	inspectPackage(pkg, listFiles)
	return nil
}

func inspectPackage(pkg cipd.Package, listFiles bool) {
	logging.Infof("Name:        %s", pkg.Name())
	logging.Infof("Instance ID: %s", pkg.InstanceID())
	if listFiles {
		logging.Infof("Package files:")
		for _, f := range pkg.Files() {
			logging.Infof("  %v", f.Name())
		}
	}
}

////////////////////////////////////////////////////////////////////////////////
// 'register' subcommand.

var cmdRegister = &subcommands.Command{
	UsageLine: "pkg-register <package file>",
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
	client, err := authenticatedClient()
	if err != nil {
		reportError("Error when authenticating: %s", err)
		return 1
	}
	err = registerPackageFile(args[0], client)
	if err != nil {
		reportError("Error while registering the package: %s", err)
		return 1
	}
	return 0
}

func registerPackageFile(packageFile string, client *http.Client) error {
	pkg, err := cipd.OpenPackageFile(packageFile, "")
	if err != nil {
		return err
	}
	defer pkg.Close()
	logging.Infof("Registering package %s:%s", pkg.Name(), pkg.InstanceID())
	inspectPackage(pkg, false)
	return cipd.RegisterPackage(cipd.RegisterPackageOptions{
		Package: pkg,
		CommonOptions: cipd.CommonOptions{
			Client: client,
		},
	})
}

////////////////////////////////////////////////////////////////////////////////
// 'upload' subcommand.

var cmdUpload = &subcommands.Command{
	UsageLine: "pkg-upload <package file>",
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
	client, err := authenticatedClient()
	if err != nil {
		reportError("Error when authenticating: %s", err)
		return 1
	}
	err = uploadPackageFile(args[0], client)
	if err != nil {
		reportError("Error while uploading the package: %s", err)
		return 1
	}
	return 0
}

func uploadPackageFile(packageFile string, client *http.Client) error {
	pkg, err := cipd.OpenPackageFile(packageFile, "")
	if err != nil {
		return err
	}
	defer pkg.Close()
	logging.Infof("Uploading package instance %s", pkg.InstanceID())
	inspectPackage(pkg, false)
	return cipd.UploadToCAS(cipd.UploadToCASOptions{
		SHA1: pkg.InstanceID(),
		Data: pkg.DataReader(),
		CommonOptions: cipd.CommonOptions{
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
		cmdInspect,
		cmdRegister,
		cmdUpload,
	},
}

func main() {
	os.Exit(subcommands.Run(application, nil))
}
