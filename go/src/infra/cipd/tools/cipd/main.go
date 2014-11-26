// Copyright 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

/*
Package infra/cipd/tools/cipd/main is client side of for Chrome Infra Package
Deployer.

TODO: write more.

Subcommand starting with 'pkg-' are low level commands operating on package
files on disk (i.e. no interaction with the server at all).
*/
package main

import (
	"crypto/rsa"
	"crypto/x509"
	"encoding/pem"
	"flag"
	"fmt"
	"io/ioutil"
	"os"
	"strings"

	"infra/cipd"

	"github.com/maruel/subcommands"
)

////////////////////////////////////////////////////////////////////////////////
// Utility functions.

// isDirectory returns true if path is pointing to an existing directory.
func isDirectory(p string) bool {
	stat, err := os.Stat(p)
	return err == nil && stat.IsDir()
}

// checkCommandLine ensures all required positional and flag-like parameters
// are set. Returns true if they are, or false (and prints to stderr) if not.
func checkCommandLine(args []string, flags *flag.FlagSet, positionalCount int) bool {
	// Check number of expected positional arguments.
	if positionalCount == 0 && len(args) != 0 {
		fmt.Fprintf(os.Stderr, "Unexpected arguments %v.\n", args)
		return false
	}
	if len(args) != positionalCount {
		fmt.Fprintf(os.Stderr, "Expecting %d arguments, got %d.\n", positionalCount, len(args))
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
		fmt.Fprintf(os.Stderr, "Missing required flags:\n")
		for _, f := range unset {
			fmt.Fprintf(os.Stderr, "  -%s: %s\n", f.Name, f.Usage)
		}
		return false
	}
	return true
}

// privateKeyFromPEM parses PEM-encode PKCS1 RSA private key.
func privateKeyFromPEM(data []byte) (*rsa.PrivateKey, error) {
	block, rest := pem.Decode(data)
	if len(rest) != 0 {
		return nil, fmt.Errorf("PEM should have one block only")
	}
	if block.Type != "RSA PRIVATE KEY" {
		return nil, fmt.Errorf("Expecting \"RSA PRIVATE KEY\" got \"%s\" instead", block.Type)
	}
	return x509.ParsePKCS1PrivateKey(block.Bytes)
}

////////////////////////////////////////////////////////////////////////////////
// 'build' subcommand.

var cmdBuild = &subcommands.Command{
	UsageLine: "pkg-build",
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
	err := buildPackage(c.packageName, c.inputDir, c.outputFile, c.signingKey)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error while building the package: %s.\n", err)
		return 1
	}
	return 0
}

func buildPackage(packageName string, inputDir string, outFile string, sigingKey string) error {
	// Read and parse signing key.
	data, err := ioutil.ReadFile(sigingKey)
	if err != nil {
		return err
	}
	privateKey, err := privateKeyFromPEM(data)
	if err != nil {
		return err
	}

	// Read the list of files to add to the package.
	files, err := cipd.ScanFileSystem(inputDir)
	if err != nil {
		return err
	}

	// Build the package.
	out, err := os.OpenFile(outFile, os.O_RDWR|os.O_CREATE|os.O_TRUNC, 0666)
	if err != nil {
		return err
	}
	defer out.Close()
	err = cipd.BuildPackage(cipd.BuildPackageOptions{
		Input:       files,
		Output:      out,
		PackageName: packageName,
	})
	if err != nil {
		return err
	}

	// Sign it.
	_, err = out.Seek(0, os.SEEK_SET)
	if err != nil {
		return err
	}
	sig, err := cipd.Sign(out, privateKey)
	if err != nil {
		return err
	}
	asBytes, err := cipd.MarshalSignatureList([]cipd.SignatureBlock{sig})
	if err != nil {
		return err
	}

	// Append the signature to the end.
	_, err = out.Seek(0, os.SEEK_END)
	if err != nil {
		return err
	}
	_, err = out.Write(asBytes)
	if err != nil {
		return err
	}
	out.Close()

	// Print information about built package, also fail if it is not readable.
	err = inspectPackage(outFile, false)
	if err != nil {
		return err
	}

	return nil
}

////////////////////////////////////////////////////////////////////////////////
// 'deploy' subcommand.

var cmdDeploy = &subcommands.Command{
	UsageLine: "pkg-deploy <package file>",
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
	packagePath := args[0]
	err := deployPackage(c.rootDir, packagePath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "%s: error while deploying the package - %s.\n", a.GetName(), err)
		return 1
	}
	return 0
}

func deployPackage(root string, packagePath string) error {
	pkg, err := cipd.OpenPackageFile(packagePath, nil)
	if err != nil {
		return err
	}
	defer pkg.Close()

	fmt.Printf("Name:        %s\n", pkg.Name())
	fmt.Printf("Instance ID: %s\n", pkg.InstanceID())
	fmt.Printf("Signed:      %v\n", pkg.Signed())
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
	packageName := args[0]
	err := inspectPackage(packageName, true)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error while inspecting the package: %s.\n", err)
		return 1
	}
	return 0
}

func inspectPackage(path string, listFiles bool) error {
	pkg, err := cipd.OpenPackageFile(path, nil)
	if err != nil {
		return err
	}
	defer pkg.Close()

	fmt.Printf("Name:        %s\n", pkg.Name())
	fmt.Printf("Instance ID: %s\n", pkg.InstanceID())
	fmt.Printf("Signed:      %v\n", pkg.Signed())
	if listFiles && pkg.Signed() {
		fmt.Printf("\nPackage files:\n")
		for _, f := range pkg.Files() {
			fmt.Printf("  %v\n", f.Name())
		}
	}

	return nil
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
	},
}

func main() {
	os.Exit(subcommands.Run(application, nil))
}
