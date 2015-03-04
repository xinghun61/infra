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
	"io/ioutil"
	"net/http"
	"os"
	"strings"

	"infra/libs/auth"
	"infra/libs/build"
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

// serviceOptions defines command line arguments related to communication
// with the remote service. Subcommands that interact with the network include
// it.
type serviceOptions struct {
	serviceURL         string
	serviceAccountJSON string
}

func (opts *serviceOptions) registerFlags(f flag.FlagSet) {
	f.StringVar(&opts.serviceURL, "service-url", "", "URL of a backend to use instead of the default one")
	f.StringVar(&opts.serviceAccountJSON, "service-account-json", "", "Path to JSON file with service account credentials to use.")
}

func (opts *serviceOptions) makeClient() (*http.Client, error) {
	authOpts := auth.Options{}
	if opts.serviceAccountJSON != "" {
		authOpts.Method = auth.ServiceAccountMethod
		authOpts.ServiceAccountJSONPath = opts.serviceAccountJSON
	}
	return auth.AuthenticatedClient(false, auth.NewAuthenticator(authOpts))
}

////////////////////////////////////////////////////////////////////////////////
// 'create' subcommand.

var cmdCreate = &subcommands.Command{
	UsageLine: "create [options]",
	ShortDesc: "builds and uploads a package instance file",
	LongDesc:  "Builds and uploads a package instance file.",
	CommandRun: func() subcommands.CommandRun {
		c := &createRun{}
		c.serviceOptions.registerFlags(c.Flags)
		c.Flags.StringVar(&c.packageName, "name", "<name>", "package name")
		c.Flags.StringVar(&c.inputDir, "in", "<path>", "path to a directory with files to package")
		return c
	},
}

type createRun struct {
	subcommands.CommandRunBase
	serviceOptions

	packageName string
	inputDir    string
}

func (c *createRun) Run(a subcommands.Application, args []string) int {
	if !checkCommandLine(args, c.GetFlags(), 0) {
		return 1
	}
	err := buildAndUploadInstance(c.packageName, c.inputDir, c.serviceOptions)
	if err != nil {
		reportError("Error while uploading the package: %s", err)
		return 1
	}
	return 0
}

func buildAndUploadInstance(packageName string, inputDir string, opts serviceOptions) error {
	f, err := ioutil.TempFile("", "cipd_pkg")
	if err != nil {
		return err
	}
	defer func() {
		f.Close()
		os.Remove(f.Name())
	}()
	err = buildInstanceFile(packageName, inputDir, f.Name())
	if err != nil {
		return err
	}
	return registerInstanceFile(f.Name(), opts)
}

////////////////////////////////////////////////////////////////////////////////
// 'ensure' subcommand.

var cmdEnsure = &subcommands.Command{
	UsageLine: "ensure [options]",
	ShortDesc: "installs, removes and updates packages",
	LongDesc:  "Installs, removes and updates packages.",
	CommandRun: func() subcommands.CommandRun {
		c := &ensureRun{}
		c.Flags.StringVar(&c.rootDir, "root", "<path>", "path to a installation site root directory")
		c.Flags.StringVar(&c.listFile, "list", "<path>", "a file with a list of '<package name> <version>' pairs")
		c.serviceOptions.registerFlags(c.Flags)
		return c
	},
}

type ensureRun struct {
	subcommands.CommandRunBase
	serviceOptions

	rootDir  string
	listFile string
}

func (c *ensureRun) Run(a subcommands.Application, args []string) int {
	if !checkCommandLine(args, c.GetFlags(), 0) {
		return 1
	}
	err := ensurePackages(c.rootDir, c.listFile, c.serviceOptions)
	if err != nil {
		reportError("Error while updating packages: %s", err)
		return 1
	}
	return 0
}

func ensurePackages(root string, desiredStateFile string, opts serviceOptions) error {
	f, err := os.Open(desiredStateFile)
	if err != nil {
		return err
	}
	defer f.Close()
	desiredState, err := cipd.ParseDesiredState(f)
	if err != nil {
		return err
	}
	return cipd.EnsurePackages(cipd.EnsurePackagesOptions{
		ServiceURL:    opts.serviceURL,
		ClientFactory: func() (*http.Client, error) { return opts.makeClient() },
		Root:          root,
		Packages:      desiredState,
	})
}

////////////////////////////////////////////////////////////////////////////////
// 'acl-list' subcommand.

var cmdListACL = &subcommands.Command{
	UsageLine: "acl-list <package subpath>",
	ShortDesc: "lists package path Access Control List",
	LongDesc:  "Lists package path Access Control List",
	CommandRun: func() subcommands.CommandRun {
		c := &listACLRun{}
		c.serviceOptions.registerFlags(c.Flags)
		return c
	},
}

type listACLRun struct {
	subcommands.CommandRunBase
	serviceOptions
}

func (c *listACLRun) Run(a subcommands.Application, args []string) int {
	if !checkCommandLine(args, c.GetFlags(), 1) {
		return 1
	}
	err := listACL(args[0], c.serviceOptions)
	if err != nil {
		reportError("Error while listing ACL: %s", err)
		return 1
	}
	return 0
}

func listACL(packagePath string, opts serviceOptions) error {
	client, err := opts.makeClient()
	if err != nil {
		return err
	}
	acls, err := cipd.FetchACL(cipd.FetchACLOptions{
		ACLOptions: cipd.ACLOptions{
			ServiceURL:  opts.serviceURL,
			Client:      client,
			PackagePath: packagePath,
		},
	})
	if err != nil {
		return err
	}

	// Split by role, drop empty ACLs.
	byRole := make(map[string][]cipd.PackageACL)
	for _, a := range acls {
		if len(a.Principals) != 0 {
			byRole[a.Role] = append(byRole[a.Role], a)
		}
	}

	listRoleACL := func(title string, acls []cipd.PackageACL) {
		logging.Infof("%s:", title)
		if len(acls) == 0 {
			logging.Infof("  none")
			return
		}
		for _, a := range acls {
			logging.Infof("  via '%s':", a.PackagePath)
			for _, u := range a.Principals {
				logging.Infof("    %s", u)
			}
		}
	}

	listRoleACL("Owners", byRole["OWNER"])
	listRoleACL("Writers", byRole["WRITER"])
	listRoleACL("Readers", byRole["READER"])

	return nil
}

////////////////////////////////////////////////////////////////////////////////
// 'acl-edit' subcommand.

// principalsList is used as custom flag value. It implements flag.Value.
type principalsList []string

func (l *principalsList) String() string {
	return fmt.Sprintf("%v", *l)
}

func (l *principalsList) Set(value string) error {
	// Ensure <type>:<id> syntax is used. Let the backend to validate the rest.
	chunks := strings.Split(value, ":")
	if len(chunks) != 2 {
		return fmt.Errorf("The string '%s' doesn't look principal id (<type>:<id>)", value)
	}
	*l = append(*l, value)
	return nil
}

var cmdEditACL = &subcommands.Command{
	UsageLine: "acl-edit [options] <package subpath>",
	ShortDesc: "modifies package path Access Control List",
	LongDesc:  "Modifies package path Access Control List",
	CommandRun: func() subcommands.CommandRun {
		c := &editACLRun{}
		c.Flags.Var(&c.owner, "owner", "users or groups to grant OWNER role")
		c.Flags.Var(&c.writer, "writer", "users or groups to grant WRITER role")
		c.Flags.Var(&c.reader, "reader", "users or groups to grant READER role")
		c.Flags.Var(&c.revoke, "revoke", "users or groups to remove from all roles")
		c.serviceOptions.registerFlags(c.Flags)
		return c
	},
}

type editACLRun struct {
	subcommands.CommandRunBase
	serviceOptions

	owner  principalsList
	writer principalsList
	reader principalsList
	revoke principalsList
}

func (c *editACLRun) Run(a subcommands.Application, args []string) int {
	if !checkCommandLine(args, c.GetFlags(), 1) {
		return 1
	}
	err := editACL(args[0], c.owner, c.writer, c.reader, c.revoke, c.serviceOptions)
	if err != nil {
		reportError("Error while editing ACL: %s", err)
		return 1
	}
	return 0
}

func editACL(packagePath string, owners, writers, readers, revoke principalsList, opts serviceOptions) error {
	changes := []cipd.PackageACLChange{}

	makeChanges := func(action cipd.PackageACLChangeAction, role string, list principalsList) {
		for _, p := range list {
			changes = append(changes, cipd.PackageACLChange{
				Action:    action,
				Role:      role,
				Principal: p,
			})
		}
	}

	makeChanges(cipd.GrantRole, "OWNER", owners)
	makeChanges(cipd.GrantRole, "WRITER", writers)
	makeChanges(cipd.GrantRole, "READER", readers)

	makeChanges(cipd.RevokeRole, "OWNER", revoke)
	makeChanges(cipd.RevokeRole, "WRITER", revoke)
	makeChanges(cipd.RevokeRole, "READER", revoke)

	if len(changes) == 0 {
		return nil
	}

	client, err := opts.makeClient()
	if err != nil {
		return err
	}

	err = cipd.ModifyACL(cipd.ModifyACLOptions{
		ACLOptions: cipd.ACLOptions{
			ServiceURL:  opts.serviceURL,
			Client:      client,
			PackagePath: packagePath,
		},
		Changes: changes,
	})
	if err != nil {
		return err
	}
	logging.Infof("ACL changes applied.")
	return nil
}

////////////////////////////////////////////////////////////////////////////////
// 'pkg-build' subcommand.

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
	// Print information about built package, also verify it is readable.
	err = inspectInstanceFile(c.outputFile, false)
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
	return nil
}

////////////////////////////////////////////////////////////////////////////////
// 'pkg-deploy' subcommand.

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
// 'pkg-fetch' subcommand.

var cmdFetch = &subcommands.Command{
	UsageLine: "pkg-fetch [options]",
	ShortDesc: "fetches a package instance file from the repository",
	LongDesc:  "Fetches a package instance file from the repository.",
	CommandRun: func() subcommands.CommandRun {
		c := &fetchRun{}
		c.Flags.StringVar(&c.packageName, "name", "<name>", "package name")
		c.Flags.StringVar(&c.instanceID, "instance-id", "<instance id>", "package instance ID to fetch")
		c.Flags.StringVar(&c.outputPath, "out", "<path>", "path to a file to write fetch to")
		c.serviceOptions.registerFlags(c.Flags)
		return c
	},
}

type fetchRun struct {
	subcommands.CommandRunBase
	serviceOptions

	packageName string
	instanceID  string
	outputPath  string
}

func (c *fetchRun) Run(a subcommands.Application, args []string) int {
	if !checkCommandLine(args, c.GetFlags(), 0) {
		return 1
	}
	err := fetchInstanceFile(c.packageName, c.instanceID, c.outputPath, c.serviceOptions)
	if err != nil {
		reportError("Error while fetching the package: %s", err)
		return 1
	}
	return 0
}

func fetchInstanceFile(packageName, instanceID, instanceFile string, opts serviceOptions) error {
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

	client, err := opts.makeClient()
	if err != nil {
		return err
	}

	err = cipd.FetchInstance(cipd.FetchInstanceOptions{
		ServiceURL:  opts.serviceURL,
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
// 'pkg-inspect' subcommand.

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
			if f.Symlink() {
				target, err := f.SymlinkTarget()
				if err != nil {
					logging.Infof(" E %s (%s)", f.Name(), err)
				} else {
					logging.Infof(" S %s -> %s", f.Name(), target)
				}
			} else {
				logging.Infof(" F %s", f.Name())
			}
		}
	}
}

////////////////////////////////////////////////////////////////////////////////
// 'pkg-register' subcommand.

var cmdRegister = &subcommands.Command{
	UsageLine: "pkg-register <package instance file>",
	ShortDesc: "uploads and registers package instance in the package repository",
	LongDesc:  "Uploads and registers package instance in the package repository.",
	CommandRun: func() subcommands.CommandRun {
		c := &registerRun{}
		c.serviceOptions.registerFlags(c.Flags)
		return c
	},
}

type registerRun struct {
	subcommands.CommandRunBase
	serviceOptions
}

func (c *registerRun) Run(a subcommands.Application, args []string) int {
	if !checkCommandLine(args, c.GetFlags(), 1) {
		return 1
	}
	err := registerInstanceFile(args[0], c.serviceOptions)
	if err != nil {
		reportError("Error while registering the package: %s", err)
		return 1
	}
	return 0
}

func registerInstanceFile(instanceFile string, opts serviceOptions) error {
	inst, err := cipd.OpenInstanceFile(instanceFile, "")
	if err != nil {
		return err
	}
	defer inst.Close()
	client, err := opts.makeClient()
	if err != nil {
		return err
	}
	logging.Infof("Registering package %s:%s", inst.PackageName(), inst.InstanceID())
	inspectInstance(inst, false)
	return cipd.RegisterInstance(cipd.RegisterInstanceOptions{
		PackageInstance: inst,
		UploadOptions: cipd.UploadOptions{
			ServiceURL: opts.serviceURL,
			Client:     client,
		},
	})
}

////////////////////////////////////////////////////////////////////////////////
// Main.

var application = &subcommands.DefaultApplication{
	Name:  "cipd",
	Title: "Chrome infra package deployer " + build.InfoString(),
	Commands: []*subcommands.Command{
		subcommands.CmdHelp,

		// High level commands.
		cmdCreate,
		cmdEnsure,

		// Authentication related commands.
		auth.SubcommandInfo("auth-info"),
		auth.SubcommandLogin("auth-login"),
		auth.SubcommandLogout("auth-logout"),

		// ACLs.
		cmdListACL,
		cmdEditACL,

		// Low level pkg-* commands.
		cmdBuild,
		cmdDeploy,
		cmdFetch,
		cmdInspect,
		cmdRegister,
	},
}

func main() {
	os.Exit(subcommands.Run(application, nil))
}
