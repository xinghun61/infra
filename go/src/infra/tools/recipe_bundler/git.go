// Copyright 2018 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package main

import (
	"os/exec"
	"strings"

	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/logging"
	"golang.org/x/net/context"
)

type gitRepo struct {
	localPath  string
	remoteRepo string
}

func (g *gitRepo) git(ctx context.Context, args ...string) error {
	run := newRunner(ctx, "gitRepo.git", "git", args)
	run.cwd = g.localPath
	return run.do()
}

func (g *gitRepo) gitQuiet(ctx context.Context, args ...string) error {
	run := newRunner(ctx, "gitRepo.git", "git", args)
	run.cwd = g.localPath
	run.suppressFail = true
	return run.do()
}

func (g *gitRepo) hasCommit(ctx context.Context, commit string) bool {
	return g.gitQuiet(ctx, "cat-file", "-e", commit+"^{commit}") == nil
}

// resolveSpec resolves any symbolic ref to a concrete ref, and resolves the
// current commit ID of that ref.
func (g *gitRepo) resolveSpec(ctx context.Context, spec fetchSpec) (ret fetchSpec, err error) {
	logging.Debugf(ctx, "gitRepo.resolveRef")
	cmd := exec.CommandContext(ctx, "git", "ls-remote", "--symref", "https://"+g.remoteRepo, spec.ref)
	out, err := cmd.CombinedOutput()
	if err != nil {
		return
	}
	// output looks like:
	//   ref: refs/heads/master\tHEAD
	//   548df237a6411a7de965ce12544cf481931b8028\tHEAD

	lines := strings.Split(strings.TrimSpace(string(out)), "\n")
	if len(lines) == 0 {
		err = errors.Reason("unknown ref %q", spec.ref).Err()
		return
	}

	ret = spec
	for _, line := range lines {
		logging.Debugf(ctx, "parsing: %q", line)
		toks := strings.SplitN(line, "\t", 2)
		if len(toks) != 2 {
			logging.Debugf(ctx, "skipping line without tab")
			continue
		}
		if toks[1] != spec.ref {
			logging.Debugf(ctx, "skipping line without HEAD")
			continue
		}
		if !strings.HasPrefix(toks[0], "ref: ") {
			if !spec.isPinned() {
				ret.revision = toks[0]
			}
		} else {
			ret.ref = strings.TrimPrefix(toks[0], "ref: ")
		}
	}
	return
}

func (g *gitRepo) ensureFetched(ctx context.Context, resolvedSpec fetchSpec) (err error) {
	if !g.hasCommit(ctx, resolvedSpec.revision) {
		err = g.git(ctx, "fetch", "--update-head-ok", "https://"+g.remoteRepo, resolvedSpec.ref+":"+resolvedSpec.ref)
	}
	return err
}
