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
	"encoding/json"
	"flag"
	"fmt"
	"io/ioutil"
	"net/http"
	"os"
	"path/filepath"
	"strings"

	"github.com/maruel/subcommands"

	"infra/libs/auth"
	"infra/libs/logging/gologger"

	"infra/tools/cipd"
	"infra/tools/cipd/common"
	"infra/tools/cipd/local"
)

var (
	log = gologger.Get()
)

////////////////////////////////////////////////////////////////////////////////
// Utility functions.

// checkCommandLine ensures all required positional and flag-like parameters
// are set. Returns true if they are, or false (and prints to stderr) if not.
func checkCommandLine(args []string, flags *flag.FlagSet, positionalCount int) bool {
	// Check number of expected positional arguments.
	if positionalCount == 0 && len(args) != 0 {
		log.Errorf("Unexpected arguments: %v", args)
		return false
	}
	if len(args) != positionalCount {
		log.Errorf("Expecting %d arguments, got %d", positionalCount, len(args))
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
		log.Errorf("Missing required flags: %v", missing)
		return false
	}
	return true
}

////////////////////////////////////////////////////////////////////////////////
// ServiceOptions mixin.

// ServiceOptions defines command line arguments related to communication
// with the remote service. Subcommands that interact with the network embed it.
type ServiceOptions struct {
	authFlags  auth.Flags
	serviceURL string
}

func (opts *ServiceOptions) registerFlags(f *flag.FlagSet) {
	f.StringVar(&opts.serviceURL, "service-url", "", "URL of a backend to use instead of the default one")
	opts.authFlags.Register(f)
}

func (opts *ServiceOptions) makeCipdClient(root string) (cipd.Client, error) {
	authOpts, err := opts.authFlags.Options()
	if err != nil {
		return nil, err
	}
	return cipd.NewClient(cipd.ClientOptions{
		ServiceURL: opts.serviceURL,
		Root:       root,
		Logger:     log,
		AuthenticatedClientFactory: func() (*http.Client, error) {
			return auth.AuthenticatedClient(auth.OptionalLogin, auth.NewAuthenticator(authOpts))
		},
	}), nil
}

////////////////////////////////////////////////////////////////////////////////
// InputOptions mixin.

// PackageVars holds array of '-pkg-var' command line options.
type PackageVars map[string]string

func (vars *PackageVars) String() string {
	// String() for empty vars used in -help output.
	if len(*vars) == 0 {
		return "key:value"
	}
	chunks := make([]string, 0, len(*vars))
	for k, v := range *vars {
		chunks = append(chunks, fmt.Sprintf("%s:%s", k, v))
	}
	return strings.Join(chunks, " ")
}

// Set is called by 'flag' package when parsing command line options.
func (vars *PackageVars) Set(value string) error {
	// <key>:<value> pair.
	chunks := strings.Split(value, ":")
	if len(chunks) != 2 {
		return fmt.Errorf("Expecting <key>:<value> pair, got %q", value)
	}
	(*vars)[chunks[0]] = chunks[1]
	return nil
}

// InputOptions defines command line arguments that specify where to get data
// for a new package. Subcommands that build packages embed it.
type InputOptions struct {
	// Path to *.yaml file with package definition.
	packageDef string
	vars       PackageVars

	// Alternative to 'pkg-def'.
	packageName string
	inputDir    string
}

func (opts *InputOptions) registerFlags(f *flag.FlagSet) {
	opts.vars = PackageVars{}

	// Interface to accept package definition file.
	f.StringVar(&opts.packageDef, "pkg-def", "", "*.yaml file that defines what to put into the package")
	f.Var(&opts.vars, "pkg-var", "variables accessible from package definition file")

	// Interface to accept a single directory (alternative to -pkg-def).
	f.StringVar(&opts.packageName, "name", "", "package name (unused with -pkg-def)")
	f.StringVar(&opts.inputDir, "in", "", "path to a directory with files to package (unused with -pkg-def)")
}

// prepareInput processes InputOptions by collecting all files to be added to
// a package and populating BuildInstanceOptions. Caller is still responsible to
// fill out Output field of BuildInstanceOptions.
func (opts *InputOptions) prepareInput() (local.BuildInstanceOptions, error) {
	out := local.BuildInstanceOptions{Logger: log}
	cmdErr := fmt.Errorf("Invalid command line options")

	// Handle -name and -in if defined. Do not allow -pkg-def and -pkg-var in that case.
	if opts.inputDir != "" {
		if opts.packageName == "" {
			log.Errorf("Missing required flag: -name")
			return out, cmdErr
		}
		if opts.packageDef != "" {
			log.Errorf("-pkg-def and -in can not be used together")
			return out, cmdErr
		}
		if len(opts.vars) != 0 {
			log.Errorf("-pkg-var and -in can not be used together")
			return out, cmdErr
		}

		// Simply enumerate files in the directory.
		var files []local.File
		files, err := local.ScanFileSystem(opts.inputDir, opts.inputDir, nil)
		if err != nil {
			return out, err
		}
		out = local.BuildInstanceOptions{
			Input:       files,
			PackageName: opts.packageName,
			Logger:      log,
		}
		return out, nil
	}

	// Handle -pkg-def case. -in is "" (already checked), reject -name.
	if opts.packageDef != "" {
		if opts.packageName != "" {
			log.Errorf("-pkg-def and -name can not be used together")
			return out, cmdErr
		}

		// Parse the file, perform variable substitution.
		f, err := os.Open(opts.packageDef)
		if err != nil {
			return out, err
		}
		defer f.Close()
		pkgDef, err := local.LoadPackageDef(f, opts.vars)
		if err != nil {
			return out, err
		}

		// Scan the file system. Package definition may use path relative to the
		// package definition file itself, so pass its location.
		log.Infof("Enumerating files to zip...")
		files, err := pkgDef.FindFiles(filepath.Dir(opts.packageDef))
		if err != nil {
			return out, err
		}
		out = local.BuildInstanceOptions{
			Input:       files,
			PackageName: pkgDef.Package,
			Logger:      log,
		}
		return out, nil
	}

	// All command line options are missing.
	log.Errorf("-pkg-def or -name/-in are required")
	return out, cmdErr
}

////////////////////////////////////////////////////////////////////////////////
// TagsOptions mixin.

// Tags holds array of '-tag' command line options.
type Tags []string

func (tags *Tags) String() string {
	// String() for empty vars used in -help output.
	if len(*tags) == 0 {
		return "key:value"
	}
	return strings.Join(*tags, " ")
}

// Set is called by 'flag' package when parsing command line options.
func (tags *Tags) Set(value string) error {
	err := common.ValidateInstanceTag(value)
	if err != nil {
		return err
	}
	*tags = append(*tags, value)
	return nil
}

// TagsOptions defines command line arguments for commands that accept a set
// of tags.
type TagsOptions struct {
	// Set of tags to attach to the package instance.
	tags Tags
}

func (opts *TagsOptions) registerFlags(f *flag.FlagSet) {
	opts.tags = []string{}
	f.Var(&opts.tags, "tag", "tag to attach to the package instance")
}

////////////////////////////////////////////////////////////////////////////////
// JSONOutputOptions mixin.

// JSONOutputOptions define -json-output option that is used to return
// structured operation result back to caller.
type JSONOutputOptions struct {
	jsonOutput string
}

func (opts *JSONOutputOptions) registerFlags(f *flag.FlagSet) {
	f.StringVar(&opts.jsonOutput, "json-output", "", "Path to write operation results to")
}

// writeJSONOutput writes result to JSON output file. It returns original error
// if it is non-nil.
func (opts *JSONOutputOptions) writeJSONOutput(result interface{}, err error) error {
	// -json-output flag wasn't specified.
	if opts.jsonOutput == "" {
		return err
	}

	// Prepare the body of the output file.
	var body struct {
		Error  string      `json:"error,omitempty"`
		Result interface{} `json:"result,omitempty"`
	}
	if err != nil {
		body.Error = err.Error()
	}
	body.Result = result
	out, e := json.MarshalIndent(&body, "", "  ")
	if e != nil {
		log.Errorf("Failed to serialize JSON output: %s", e)
		if err == nil {
			err = e
		}
		return err
	}

	e = ioutil.WriteFile(opts.jsonOutput, out, 0600)
	if e != nil {
		log.Errorf("Failed write JSON output to %s: %s", opts.jsonOutput, e)
		if err == nil {
			err = e
		}
		return err
	}

	return err
}

////////////////////////////////////////////////////////////////////////////////
// 'create' subcommand.

var cmdCreate = &subcommands.Command{
	UsageLine: "create [options]",
	ShortDesc: "builds and uploads a package instance file",
	LongDesc:  "Builds and uploads a package instance file.",
	CommandRun: func() subcommands.CommandRun {
		c := &createRun{}
		c.InputOptions.registerFlags(&c.Flags)
		c.TagsOptions.registerFlags(&c.Flags)
		c.ServiceOptions.registerFlags(&c.Flags)
		c.JSONOutputOptions.registerFlags(&c.Flags)
		return c
	},
}

type createRun struct {
	subcommands.CommandRunBase
	InputOptions
	TagsOptions
	ServiceOptions
	JSONOutputOptions
}

func (c *createRun) Run(a subcommands.Application, args []string) int {
	if !checkCommandLine(args, c.GetFlags(), 0) {
		return 1
	}
	pin, err := buildAndUploadInstance(c.InputOptions, c.TagsOptions, c.ServiceOptions)
	err = c.writeJSONOutput(&pin, err)
	if err != nil {
		log.Errorf("Error while uploading the package: %s", err)
		return 1
	}
	return 0
}

func buildAndUploadInstance(inputOpts InputOptions, tagsOpts TagsOptions, serviceOpts ServiceOptions) (common.Pin, error) {
	f, err := ioutil.TempFile("", "cipd_pkg")
	if err != nil {
		return common.Pin{}, err
	}
	defer func() {
		f.Close()
		os.Remove(f.Name())
	}()
	err = buildInstanceFile(f.Name(), inputOpts)
	if err != nil {
		return common.Pin{}, err
	}
	return registerInstanceFile(f.Name(), tagsOpts, serviceOpts)
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
		c.ServiceOptions.registerFlags(&c.Flags)
		return c
	},
}

type ensureRun struct {
	subcommands.CommandRunBase
	ServiceOptions

	rootDir  string
	listFile string
}

func (c *ensureRun) Run(a subcommands.Application, args []string) int {
	if !checkCommandLine(args, c.GetFlags(), 0) {
		return 1
	}
	err := ensurePackages(c.rootDir, c.listFile, c.ServiceOptions)
	if err != nil {
		log.Errorf("Error while updating packages: %s", err)
		return 1
	}
	return 0
}

func ensurePackages(root string, desiredStateFile string, serviceOpts ServiceOptions) error {
	f, err := os.Open(desiredStateFile)
	if err != nil {
		return err
	}
	defer f.Close()
	client, err := serviceOpts.makeCipdClient(root)
	if err != nil {
		return err
	}
	desiredState, err := client.ProcessEnsureFile(f)
	if err != nil {
		return err
	}
	return client.EnsurePackages(desiredState)
}

////////////////////////////////////////////////////////////////////////////////
// 'resolve' subcommand.

var cmdResolve = &subcommands.Command{
	UsageLine: "resolve [options]",
	ShortDesc: "returns concrete package instance ID given a version",
	LongDesc:  "Returns concrete package instance ID given a version.",
	CommandRun: func() subcommands.CommandRun {
		c := &resolveRun{}
		c.Flags.StringVar(&c.packageName, "name", "<name>", "package name")
		c.Flags.StringVar(&c.version, "version", "<version>", "package version to resolve")
		c.ServiceOptions.registerFlags(&c.Flags)
		c.JSONOutputOptions.registerFlags(&c.Flags)
		return c
	},
}

type resolveRun struct {
	subcommands.CommandRunBase
	ServiceOptions
	JSONOutputOptions

	packageName string
	version     string
}

func (c *resolveRun) Run(a subcommands.Application, args []string) int {
	if !checkCommandLine(args, c.GetFlags(), 0) {
		return 1
	}
	pin, err := resolveVersion(c.packageName, c.version, c.ServiceOptions)
	err = c.writeJSONOutput(&pin, err)
	if err != nil {
		log.Errorf("%s", err)
		return 1
	}
	log.Infof("Instance: %s", pin)
	return 0
}

func resolveVersion(packageName, version string, serviceOpts ServiceOptions) (common.Pin, error) {
	client, err := serviceOpts.makeCipdClient("")
	if err != nil {
		return common.Pin{}, err
	}
	return client.ResolveVersion(packageName, version)
}

////////////////////////////////////////////////////////////////////////////////
// 'acl-list' subcommand.

var cmdListACL = &subcommands.Command{
	UsageLine: "acl-list <package subpath>",
	ShortDesc: "lists package path Access Control List",
	LongDesc:  "Lists package path Access Control List",
	CommandRun: func() subcommands.CommandRun {
		c := &listACLRun{}
		c.ServiceOptions.registerFlags(&c.Flags)
		return c
	},
}

type listACLRun struct {
	subcommands.CommandRunBase
	ServiceOptions
}

func (c *listACLRun) Run(a subcommands.Application, args []string) int {
	if !checkCommandLine(args, c.GetFlags(), 1) {
		return 1
	}
	err := listACL(args[0], c.ServiceOptions)
	if err != nil {
		log.Errorf("Error while listing ACL: %s", err)
		return 1
	}
	return 0
}

func listACL(packagePath string, serviceOpts ServiceOptions) error {
	client, err := serviceOpts.makeCipdClient("")
	if err != nil {
		return err
	}
	acls, err := client.FetchACL(packagePath)
	if err != nil {
		return err
	}

	// Split by role, drop empty ACLs.
	byRole := map[string][]cipd.PackageACL{}
	for _, a := range acls {
		if len(a.Principals) != 0 {
			byRole[a.Role] = append(byRole[a.Role], a)
		}
	}

	listRoleACL := func(title string, acls []cipd.PackageACL) {
		log.Infof("%s:", title)
		if len(acls) == 0 {
			log.Infof("  none")
			return
		}
		for _, a := range acls {
			log.Infof("  via '%s':", a.PackagePath)
			for _, u := range a.Principals {
				log.Infof("    %s", u)
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
		return fmt.Errorf("The string %q doesn't look principal id (<type>:<id>)", value)
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
		c.ServiceOptions.registerFlags(&c.Flags)
		return c
	},
}

type editACLRun struct {
	subcommands.CommandRunBase
	ServiceOptions

	owner  principalsList
	writer principalsList
	reader principalsList
	revoke principalsList
}

func (c *editACLRun) Run(a subcommands.Application, args []string) int {
	if !checkCommandLine(args, c.GetFlags(), 1) {
		return 1
	}
	err := editACL(args[0], c.owner, c.writer, c.reader, c.revoke, c.ServiceOptions)
	if err != nil {
		log.Errorf("Error while editing ACL: %s", err)
		return 1
	}
	return 0
}

func editACL(packagePath string, owners, writers, readers, revoke principalsList, serviceOpts ServiceOptions) error {
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

	client, err := serviceOpts.makeCipdClient("")
	if err != nil {
		return err
	}
	err = client.ModifyACL(packagePath, changes)
	if err != nil {
		return err
	}
	log.Infof("ACL changes applied.")
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
		c.InputOptions.registerFlags(&c.Flags)
		c.JSONOutputOptions.registerFlags(&c.Flags)
		c.Flags.StringVar(&c.outputFile, "out", "<path>", "path to a file to write the final package to")
		return c
	},
}

type buildRun struct {
	subcommands.CommandRunBase
	InputOptions
	JSONOutputOptions

	outputFile string
}

func (c *buildRun) Run(a subcommands.Application, args []string) int {
	if !checkCommandLine(args, c.GetFlags(), 0) {
		return 1
	}
	err := buildInstanceFile(c.outputFile, c.InputOptions)
	if err != nil {
		log.Errorf("Error while building the package: %s", err)
		return 1
	}
	// Print information about built package, also verify it is readable.
	pin, err := inspectInstanceFile(c.outputFile, false)
	err = c.writeJSONOutput(&pin, err)
	if err != nil {
		log.Errorf("Error while building the package: %s", err)
		return 1
	}
	return 0
}

func buildInstanceFile(instanceFile string, inputOpts InputOptions) error {
	// Read the list of files to add to the package.
	buildOpts, err := inputOpts.prepareInput()
	if err != nil {
		return err
	}

	// Prepare the destination, update build options with io.Writer to it.
	out, err := os.OpenFile(instanceFile, os.O_RDWR|os.O_CREATE|os.O_TRUNC, 0666)
	if err != nil {
		return err
	}
	buildOpts.Output = out

	// Build the package.
	err = local.BuildInstance(buildOpts)
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
		log.Errorf("Error while deploying the package: %s", err)
		return 1
	}
	return 0
}

func deployInstanceFile(root string, instanceFile string) error {
	inst, err := local.OpenInstanceFile(instanceFile, "")
	if err != nil {
		return err
	}
	defer inst.Close()
	inspectInstance(inst, false)
	_, err = local.NewDeployer(root, log).DeployInstance(inst)
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
		c.Flags.StringVar(&c.version, "version", "<version>", "package version to fetch")
		c.Flags.StringVar(&c.outputPath, "out", "<path>", "path to a file to write fetch to")
		c.ServiceOptions.registerFlags(&c.Flags)
		return c
	},
}

type fetchRun struct {
	subcommands.CommandRunBase
	ServiceOptions

	packageName string
	version     string
	outputPath  string
}

func (c *fetchRun) Run(a subcommands.Application, args []string) int {
	if !checkCommandLine(args, c.GetFlags(), 0) {
		return 1
	}
	err := fetchInstanceFile(c.packageName, c.version, c.outputPath, c.ServiceOptions)
	if err != nil {
		log.Errorf("Error while fetching the package: %s", err)
		return 1
	}
	return 0
}

func fetchInstanceFile(packageName, version, instanceFile string, serviceOpts ServiceOptions) error {
	client, err := serviceOpts.makeCipdClient("")
	if err != nil {
		return err
	}
	pin, err := client.ResolveVersion(packageName, version)
	if err != nil {
		return err
	}

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

	err = client.FetchInstance(pin, out)
	if err != nil {
		return err
	}

	// Verify it (by checking that instanceID matches the file content).
	out.Close()
	ok = true
	inst, err := local.OpenInstanceFile(instanceFile, pin.InstanceID)
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
		c := &inspectRun{}
		c.JSONOutputOptions.registerFlags(&c.Flags)
		return c
	},
}

type inspectRun struct {
	subcommands.CommandRunBase
	JSONOutputOptions
}

func (c *inspectRun) Run(a subcommands.Application, args []string) int {
	if !checkCommandLine(args, c.GetFlags(), 1) {
		return 1
	}
	pin, err := inspectInstanceFile(args[0], true)
	err = c.writeJSONOutput(&pin, err)
	if err != nil {
		log.Errorf("Error while inspecting the package: %s", err)
		return 1
	}
	return 0
}

func inspectInstanceFile(instanceFile string, listFiles bool) (common.Pin, error) {
	inst, err := local.OpenInstanceFile(instanceFile, "")
	if err != nil {
		return common.Pin{}, err
	}
	defer inst.Close()
	inspectInstance(inst, listFiles)
	return inst.Pin(), nil
}

func inspectInstance(inst local.PackageInstance, listFiles bool) {
	log.Infof("Instance: %s", inst.Pin())
	if listFiles {
		log.Infof("Package files:")
		for _, f := range inst.Files() {
			if f.Symlink() {
				target, err := f.SymlinkTarget()
				if err != nil {
					log.Infof(" E %s (%s)", f.Name(), err)
				} else {
					log.Infof(" S %s -> %s", f.Name(), target)
				}
			} else {
				log.Infof(" F %s", f.Name())
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
		c.TagsOptions.registerFlags(&c.Flags)
		c.ServiceOptions.registerFlags(&c.Flags)
		c.JSONOutputOptions.registerFlags(&c.Flags)
		return c
	},
}

type registerRun struct {
	subcommands.CommandRunBase
	TagsOptions
	ServiceOptions
	JSONOutputOptions
}

func (c *registerRun) Run(a subcommands.Application, args []string) int {
	if !checkCommandLine(args, c.GetFlags(), 1) {
		return 1
	}
	pin, err := registerInstanceFile(args[0], c.TagsOptions, c.ServiceOptions)
	err = c.writeJSONOutput(&pin, err)
	if err != nil {
		log.Errorf("Error while registering the package: %s", err)
		return 1
	}
	return 0
}

func registerInstanceFile(instanceFile string, tagsOpts TagsOptions, serviceOpts ServiceOptions) (common.Pin, error) {
	inst, err := local.OpenInstanceFile(instanceFile, "")
	if err != nil {
		return common.Pin{}, err
	}
	defer inst.Close()
	client, err := serviceOpts.makeCipdClient("")
	if err != nil {
		return common.Pin{}, err
	}
	inspectInstance(inst, false)
	err = client.RegisterInstance(inst)
	if err != nil {
		return common.Pin{}, err
	}
	err = client.AttachTagsWhenReady(inst.Pin(), tagsOpts.tags)
	if err != nil {
		return common.Pin{}, err
	}
	return inst.Pin(), nil
}

////////////////////////////////////////////////////////////////////////////////
// Main.

var application = &subcommands.DefaultApplication{
	Name:  "cipd",
	Title: "Chrome infra package deployer",
	Commands: []*subcommands.Command{
		subcommands.CmdHelp,

		// High level commands.
		cmdCreate,
		cmdEnsure,
		cmdResolve,

		// Authentication related commands.
		auth.SubcommandInfo(auth.Options{Logger: log}, "auth-info"),
		auth.SubcommandLogin(auth.Options{Logger: log}, "auth-login"),
		auth.SubcommandLogout(auth.Options{Logger: log}, "auth-logout"),

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
