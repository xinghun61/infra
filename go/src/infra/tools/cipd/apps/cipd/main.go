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
	"bytes"
	"crypto/rsa"
	"crypto/x509"
	"encoding/pem"
	"flag"
	"fmt"
	"io/ioutil"
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
		reportError("Missing required flags: %v")
		return false
	}
	return true
}

// readPrivateKey reads PEM encoded file with RSA private key.
func readPrivateKey(file string) (*rsa.PrivateKey, error) {
	data, err := ioutil.ReadFile(file)
	if err != nil {
		return nil, err
	}
	block, rest := pem.Decode(data)
	if len(rest) != 0 {
		return nil, fmt.Errorf("PEM should have one block only")
	}
	if block.Type != "RSA PRIVATE KEY" {
		return nil, fmt.Errorf("Expecting \"RSA PRIVATE KEY\" got \"%s\" instead", block.Type)
	}
	return x509.ParsePKCS1PrivateKey(block.Bytes)
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
	LongDesc:  "Builds and signs a package producing *.cipd file.",
	CommandRun: func() subcommands.CommandRun {
		c := &buildRun{}
		c.Flags.StringVar(&c.packageName, "name", "<name>", "package name")
		c.Flags.StringVar(&c.inputDir, "in", "<path>", "path to a directory with files to package")
		c.Flags.StringVar(&c.outputFile, "out", "<path>", "path to a file to write the final package to")
		c.Flags.StringVar(&c.signingKey, "signing-key", "<path>", "path to PEM encoded PKCS1 RSA private key to use for signing")
		return c
	},
}

type buildRun struct {
	subcommands.CommandRunBase
	packageName string
	inputDir    string
	outputFile  string
	signingKey  string
}

func (c *buildRun) Run(a subcommands.Application, args []string) int {
	if !checkCommandLine(args, c.GetFlags(), 0) {
		return 1
	}
	err := buildPackageFile(c.packageName, c.inputDir, c.outputFile, c.signingKey)
	if err != nil {
		reportError("Error while building the package: %s", err)
		return 1
	}
	return 0
}

func buildPackageFile(packageName string, inputDir string, packageFile string, signingKeyFile string) error {
	// Read and parse signing key.
	privateKey, err := readPrivateKey(signingKeyFile)
	if err != nil {
		return err
	}

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
	if err != nil {
		out.Close()
		os.Remove(packageFile)
		return err
	}

	// Sign it.
	err = cipd.SignFile(out, privateKey)
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
	LongDesc:  "Deployed a signed *.cipd package into a site root.",
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
	pkg, err := cipd.OpenPackageFile(packageFile, nil)
	if err != nil {
		return err
	}
	defer pkg.Close()
	inspectPackage(pkg, false)
	if !pkg.Signed() {
		return fmt.Errorf("Package is not signed, refusing to deploy")
	}
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
	pkg, err := cipd.OpenPackageFile(packageFile, nil)
	if err != nil {
		return err
	}
	defer pkg.Close()
	inspectPackage(pkg, listFiles)
	return nil
}

func inspectPackage(pkg cipd.Package, listFiles bool) {
	// General info. Name is in the manifest that is only accessed when package
	// signature is verified.
	if !pkg.Signed() {
		logging.Infof("Name:        %s", pkg.Name())
	}
	logging.Infof("Instance ID: %s", pkg.InstanceID())
	logging.Infof("Signed:      %v", pkg.Signed())

	// List of public keys used to sign a package.
	signatures := pkg.Signatures()
	verifiedSigs := pkg.VerifiedSignatures()
	if len(signatures) != 0 {
		logging.Infof("Signed by public keys:")
		for _, s := range signatures {
			verified := "not verified"
			for _, verifiedSig := range verifiedSigs {
				if bytes.Equal(s.Signature, verifiedSig.Signature) {
					verified = "verified"
					break
				}
			}
			logging.Infof("  %s (%s)", s.SignatureKey, verified)
		}
	}

	// List of files.
	if listFiles && pkg.Signed() {
		logging.Infof("Package files:")
		for _, f := range pkg.Files() {
			logging.Infof("  %v", f.Name())
		}
	}
}

////////////////////////////////////////////////////////////////////////////////
// 'sign' subcommand.

var cmdSign = &subcommands.Command{
	UsageLine: "pkg-sign [options] <package file>",
	ShortDesc: "signs a package file with a private key",
	LongDesc:  "Signs a package file with a private key, appending the signature to the end",
	CommandRun: func() subcommands.CommandRun {
		c := &signRun{}
		c.Flags.StringVar(&c.signingKey, "signing-key", "<path>", "path to PEM encoded PKCS1 RSA private key to use for signing")
		return c
	},
}

type signRun struct {
	subcommands.CommandRunBase
	signingKey string
}

func (c *signRun) Run(a subcommands.Application, args []string) int {
	if !checkCommandLine(args, c.GetFlags(), 1) {
		return 1
	}
	err := signPackageFile(args[0], c.signingKey)
	if err != nil {
		reportError("Error while signing the package: %s", err)
		return 1
	}
	return 0
}

func signPackageFile(packageFile string, signingKeyFile string) error {
	privateKey, err := readPrivateKey(signingKeyFile)
	if err != nil {
		return err
	}
	file, err := os.OpenFile(packageFile, os.O_RDWR, 0666)
	if err != nil {
		return err
	}
	err = cipd.SignFile(file, privateKey)
	file.Close()
	if err != nil {
		return err
	}
	return inspectPackageFile(packageFile, false)
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
	pkg, err := cipd.OpenPackageFile(packageFile, nil)
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
		cmdSign,
		cmdUpload,
	},
}

func main() {
	os.Exit(subcommands.Run(application, nil))
}
