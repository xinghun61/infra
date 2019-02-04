// Copyright 2017 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package main

import (
	"context"
	"fmt"
	"net/http"
	"net/url"
	"strconv"
	"strings"

	gerrit "github.com/andygrunwald/go-gerrit"

	buildbucketpb "go.chromium.org/luci/buildbucket/proto"
	"go.chromium.org/luci/common/errors"
)

type gerritCL struct {
	buildbucketpb.GerritChange

	// blamelist == [blame]
	blame string
}

func getStrMap(m map[string]interface{}, key ...string) map[string]interface{} {
	for _, k := range key {
		sub, _ := m[k].(map[string]interface{})
		if sub == nil {
			sub = map[string]interface{}{}
			m[k] = sub
		}
		m = sub
	}
	return m
}

func getStrMapInList(m map[string]interface{}, key string, idx int) map[string]interface{} {
	lst, _ := m[key].([]interface{})
	if lst == nil {
		lst = []interface{}{}
		m[key] = lst
	}
	for len(lst) <= idx {
		lst = append(lst, map[string]interface{}{})
	}
	m[key] = lst
	ret, ok := lst[idx].(map[string]interface{})
	if !ok {
		ret = map[string]interface{}{}
		lst[idx] = ret
	}
	return ret
}

func (g *gerritCL) setProperties(properties map[string]interface{}, atIndex int) {
	properties["repository"] = fmt.Sprintf("https://%s/%s", g.Host, g.Project)
	properties["blamelist"] = []string{g.blame}

	input := getStrMap(properties, "$recipe_engine/buildbucket", "build", "input")
	gerritChanges := getStrMapInList(input, "gerritChanges", atIndex)

	gerritChanges["change"] = strconv.FormatInt(g.Change, 10)
	gerritChanges["host"] = g.Host
	gerritChanges["patchset"] = strconv.FormatInt(g.Patchset, 10)
	gerritChanges["project"] = g.Project
}

func (g *gerritCL) loadRemoteData(ctx context.Context, authClient *http.Client) error {
	gc, err := gerrit.NewClient("https://"+g.Host, authClient)
	if err != nil {
		return errors.Annotate(err, "creating new gerrit client").Err()
	}

	ci, _, err := gc.Changes.GetChangeDetail(strconv.FormatInt(g.Change, 10), &gerrit.ChangeOptions{
		AdditionalFields: []string{"ALL_REVISIONS", "DOWNLOAD_COMMANDS"}})
	if err != nil {
		return errors.Annotate(err, "GetChangeDetail").Err()
	}

	g.Project = ci.Project
	for commitID, rd := range ci.Revisions {
		if int64(rd.Number) == g.Patchset || (g.Patchset == 0 && commitID == ci.CurrentRevision) {
			g.Patchset = int64(rd.Number)
			g.blame = rd.Uploader.Email
			break
		}
	}

	return nil
}

func urlTrimSplit(path string) []string {
	ret := strings.Split(strings.Trim(path, "/"), "/")
	// empty paths can return a single empty token
	if len(ret) == 1 && ret[0] == "" {
		ret = nil
	}
	return ret
}

// parseGerrit is a helper to parse ethier the url.Path or url.Fragment.
//
// toks should be [<issue>, <patchset>] or [<issue>]
func parseGerrit(p *url.URL, toks []string) (ret *gerritCL, err error) {
	ret = &gerritCL{}
	ret.Host = p.Host
	switch len(toks) {
	case 2:
		if ret.Patchset, err = strconv.ParseInt(toks[1], 10, 0); err != nil {
			return
		}
		fallthrough
	case 1:
		ret.Change, err = strconv.ParseInt(toks[0], 10, 0)
	default:
		err = errors.New("unrecognized URL")
	}
	return
}

func parseCrChangeListURL(clURL string) (*gerritCL, error) {
	p, err := url.Parse(clURL)
	if err != nil {
		err = errors.Annotate(err, "URL_TO_CHANGELIST is invalid").Err()
		return nil, err
	}
	toks := urlTrimSplit(p.Path)
	if len(toks) == 0 || toks[0] == "c" || strings.Contains(p.Hostname(), "googlesource") {
		if len(toks) == 0 {
			// https://<gerrit_host>/#/c/<issue>
			// https://<gerrit_host>/#/c/<issue>/<patchset>
			toks = urlTrimSplit(p.Fragment)
			if len(toks) < 1 || toks[0] != "c" {
				return nil, errors.Reason("bad format for (old) gerrit URL: %q", clURL).Err()
			}
			toks = toks[1:] // remove "c"
		} else if len(toks) == 1 {
			// https://<gerrit_host>/<issue>
			// toks is already in the correct form
		} else {
			toks = toks[1:] // remove "c"
			// https://<gerrit_host>/c/<issue>
			// https://<gerrit_host>/c/<issue>/<patchset>
			// https://<gerrit_host>/c/<project/path>/+/<issue>
			// https://<gerrit_host>/c/<project/path>/+/<issue>/<patchset>
			for i, tok := range toks {
				if tok == "+" {
					toks = toks[i+1:]
					break
				}
			}
		}
		// toks should be [<issue>] or [<issue>, <patchset>] at this point
		ret, err := parseGerrit(p, toks)
		err = errors.Annotate(err, "bad format for gerrit URL: %q", clURL).Err()
		return ret, err
	}

	return nil, errors.Reason("Unknown changelist URL format: %q", clURL).Err()
}

// ChromiumCL edits the chromium-recipe-specific properties pertaining to
// a "tryjob" CL. These properties include things like "patch_storage", "issue",
// etc.
func (ejd *EditJobDefinition) ChromiumCL(ctx context.Context, authClient *http.Client, patchsetURL string, atIndex int) {
	if patchsetURL == "" {
		return
	}
	ejd.tweakUserland(func(u *Userland) error {
		// parse patchsetURL to see if we understand it
		clImpl, err := parseCrChangeListURL(patchsetURL)
		if err != nil {
			return errors.Annotate(err, "parsing changelist URL").Err()
		}

		// make some RPCs to the underlying service to extract the rest of the
		// properties.
		if err := clImpl.loadRemoteData(ctx, authClient); err != nil {
			return errors.Annotate(err, "loading remote data").Err()
		}

		// wipe out all the old properties
		toDel := []string{
			"blamelist", "issue", "patch_gerrit_url", "patch_issue", "patch_project",
			"patch_ref", "patch_repository_url", "patch_set", "patch_storage",
			"patchset", "repository", "rietveld", "buildbucket",
		}
		for _, key := range toDel {
			delete(u.RecipeProperties, key)
		}

		// set the properties.
		clImpl.setProperties(u.RecipeProperties, atIndex)

		return nil
	})
}
