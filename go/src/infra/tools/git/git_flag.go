// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"net/url"
	"path"
	"path/filepath"
	"strings"
)

// GitFlagSplitter is a FlagSplitter configured to split against Git's top-level
// command-line flags.
//
//	$ git version
//	git version 2.12.2.564.g063fe858b8
//
//	$ git --help
//	usage: git [--version] [--help] [-C <path>] [-c name=value]
//	        [--exec-path[=<path>]] [--html-path] [--man-path] [--info-path]
//	        [-p | --paginate | --no-pager] [--no-replace-objects] [--bare]
//	        [--git-dir=<path>] [--work-tree=<path>] [--namespace=<name>]
//	        <command> [<args>]
//
// The "usage" string is here for reference, but is not complete. See `man git`
// for the full list of flags represented here.
var GitFlagSplitter = FlagSplitterDef{
	Solitary: []string{
		"--version",
		"--help",
		"--html-path",
		"--man-path",
		"--info-path",
		"-p", "--paginate",
		"--no-pager",
		"--bare",
		"--no-replace-objects",
		"--literal-pathspecs",
		"--glob-pathspecs",
		"--noglob-pathspecs",
		"--icase-pathspecs",
	},
	WithArg: []string{
		"-C",
		"-c",
	},
	WithArgAllowConjoined: []string{
		"--exec-path",
		"--git-dir",
		"--work-tree",
		"--namespace",
		"--super-prefix",
	},
}.Compile()

// GitCloneFlagSplitter is a FlagSplitter configured to split against Git's
// "clone" subcommand arguments.
//
// usage: git clone [--template=<template_directory>]
//         [-l] [-s] [--no-hardlinks] [-q] [-n] [--bare] [--mirror]
//         [-o <name>] [-b <name>] [-u <upload-pack>] [--reference <repository>]
//         [--dissociate] [--separate-git-dir <git dir>]
//         [--depth <depth>] [--[no-]single-branch]
//         [--recurse-submodules] [--[no-]shallow-submodules]
//         [--jobs <n>] [--] <repository> [<directory>]
//
// The "usage" string is here for reference, but is not complete. See
// `man git-clone` for the full list of flags represented here.
var GitCloneFlagSplitter = FlagSplitterDef{
	Solitary: []string{
		"--local", "-l",
		"--no-hardlinks",
		"--shared", "-s",
		"--disassociate",
		"--quiet", "-q",
		"--verbose", "-v",
		"--progress",
		"--no-checkout", "-n",
		"--bare",
		"--mirror",
		"--single-branch", "--no-single-branch",
		"--shallow-submodules", "--no-shallow-submodules",
	},
	SolitaryAllowConjoined: []string{
		"--recurse-submodules",
	},
	WithArgAllowConjoined: []string{
		"-b", "-u",
		"--reference", "--reference-if-able",
		"--origin", "-o",
		"--branch", "-b",
		"--upload-pack", "-u",
		"--template",
		"--config", "-c",
		"--depth",
		"--shallow-since",
		"--shallow-exclude",
		"--separate-git-dir",
		"-j", "--jobs",
	},
}.Compile()

// GitArgs is a generic interface for parsed Git arguments.
type GitArgs interface {
	// Base returns the base parsed Git args.
	Base() *BaseGitArgs

	// IsVersion returns true if the args describe a Git version request.
	IsVersion() bool

	// MayBeRemote returns true if the args may contact a remote service.
	MayBeRemote() bool
}

// BaseGitArgs represents generic parsed Git arguments.
//
// It can be generated from a generic command-line interface using ParseGitArgs.
type BaseGitArgs struct {
	// GitFlags is the set of top-level flags passed to the Git command.
	GitFlags []string

	// Subcommand, if not empty, is the Git subcommand that is being executed.
	Subcommand string

	// SubcommandArgs is the set of arguments that are passed to the subcommand.
	//
	// If Subcommand is empty, this will be empty, too.
	SubcommandArgs []string

	// Unknown is the set of unknown flags / arguments.
	Unknown []string
}

// ParseGitArgs parses command-line arguments (including the Git invocation)
// into a GitArgs.
func ParseGitArgs(args ...string) GitArgs {
	var ga BaseGitArgs

	var pos []string
	ga.GitFlags, pos, ga.Unknown = GitFlagSplitter.Split(args, true)

	if len(pos) > 0 {
		ga.Subcommand, ga.SubcommandArgs = pos[0], pos[1:]
	}

	// Parse into subcommand-specific structures.
	switch ga.Subcommand {
	case "clone":
		return parseGitCloneArgs(&ga)

	default:
		return &ga
	}
}

// Base implements GitArgs.
func (ga *BaseGitArgs) Base() *BaseGitArgs { return ga }

// IsVersion implements GitArgs.
func (ga *BaseGitArgs) IsVersion() bool {
	if ga.Subcommand == "version" {
		return true
	}
	for _, f := range ga.GitFlags {
		if f == "--version" {
			return true
		}
	}
	return false
}

// MayBeRemote implements GitArgs.
func (ga *BaseGitArgs) MayBeRemote() bool {
	switch ga.Subcommand {
	case "clone", "fetch", "ls-remote", "pull", "push", "fetch-pack", "http-fetch",
		"http-push", "send-pack", "upload-archive", "upload-pack":
		return true

	default:
		return false
	}
}

// GitCloneArgs is a specialized version of GitArgs that holds additional
// parameters for the "clone" subcommand.
type GitCloneArgs struct {
	*BaseGitArgs

	// Repository is the repository to clone.
	Repository string
	// Directory is the (optional) destination direectory to clone into. If
	// empty, the destination is derived from Repository.
	Directory string
}

func parseGitCloneArgs(ga *BaseGitArgs) GitArgs {
	gca := GitCloneArgs{
		BaseGitArgs: ga,
	}

	_, pos, _ := GitCloneFlagSplitter.Split(ga.SubcommandArgs, false)
	switch len(pos) {
	case 2:
		// Destination is explicit.
		gca.Directory = pos[1]
		fallthrough
	case 1:
		// Destination is determined by the source repository.
		gca.Repository = pos[0]
	}

	return &gca
}

// TargetDir attempts to identify the "git clone" target destination directory
// from the parsed arguments.
//
// If the directory could not be determined, TargetDir returns an empty string.
func (ga *GitCloneArgs) TargetDir() string {
	switch {
	case ga.Directory != "":
		return ga.Directory
	case ga.Repository != "":
		return sourceRepositoryName(ga.Repository)
	default:
		return ""
	}
}

func sourceRepositoryName(v string) string {
	candidateNameFromRepo := func(v string) string {
		// See if we can parse "v" as a URL.
		u, err := url.Parse(v)
		if err != nil {
			// Not a URL. Grab the final path element.
			return filepath.Base(v)
		}

		// Use our URL Path (https://.../repository) or Opaque (foo:bar).
		v = u.Path
		if v == "" {
			v = u.Opaque
		}

		// Remove trailing slashes (e.g., "https://.../repo.git/").
		v = strings.TrimSuffix(v, "/")

		// If the repository ends in ".git", remove that, too.
		v = strings.TrimSuffix(v, ".git")

		// Grab the last path element.
		if strings.HasSuffix(v, "/") {
			// Empty directory element after trimming.
			return ""
		}
		return path.Base(v)
	}

	switch candidate := candidateNameFromRepo(v); candidate {
	case ".", "..":
		// Illegal names, must reference a subdirectory.
		return ""

	default:
		return candidate
	}
}
