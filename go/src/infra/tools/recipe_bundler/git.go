// Copyright 2018 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package main

import (
	"os/exec"
	"path"
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

// resolveSpec resolves any symbolic ref, or ref glob, to an array of concrete
// refs, and resolves the current commit ID of each ref.
func (g *gitRepo) resolveSpec(ctx context.Context, spec fetchSpec) (ret []fetchSpec, err error) {
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

	ret = make([]fetchSpec, 0, len(lines))
	// Map of symbolic ref name to concrete ref name.
	syms := make(map[string]string)
	for _, line := range lines {
		logging.Debugf(ctx, "parsing: %q", line)
		toks := strings.SplitN(line, "\t", 2)
		if len(toks) != 2 {
			logging.Debugf(ctx, "skipping line without tab")
			continue
		}
		// Git's ref globbing logic is close enough to path's globbing logic,
		// so just use that to verify 'ls-remote' glob matches.
		matched, _ := path.Match(spec.ref, toks[1])
		if !matched {
			logging.Debugf(ctx, "Skipping line without '%q' ref", spec.ref)
			continue
		}
		if !strings.HasPrefix(toks[0], "ref: ") {
			ret = append(ret, spec)
			if !spec.isPinned() {
				ret[len(ret)-1].revision = toks[0]
			}
			// Replace any glob ref with the resolved ref.
			if toks[1] != spec.ref {
				ret[len(ret)-1].ref = toks[1]
			}
		} else {
			// Store symbolic ref lines to fully resolve after all the other results
			// are processed.
			syms[toks[1]] = strings.TrimPrefix(toks[0], "ref: ")
		}
	}
	if len(ret) == 0 {
		ret = append(ret, spec)
	}

	// Find any specs that contain a symbolic ref, and substitute that ref's
	// concrete ref (e.g. deadbeef,HEAD -> deadbeef,refs/heads/master)
	for i := range ret {
		if concreteRef, ok := syms[ret[i].ref]; ok {
			ret[i].ref = concreteRef
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
