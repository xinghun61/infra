// Copyright 2017 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package main

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"net/url"
	"strconv"
	"strings"

	"github.com/andygrunwald/go-gerrit"

	"go.chromium.org/luci/common/errors"
)

type gerritCL struct {
	// patch_gerrit_url == https://host
	host string
	// patch_issue
	issue uint64
	// patch_set
	patchset uint64

	// patch_project
	patchProject string

	// patch_ref
	patchRef string

	// patch_repository_url
	// repository
	repository string

	// blamelist == [blame]
	blame string
}

func (g *gerritCL) getProperties() map[string]interface{} {
	return map[string]interface{}{
		"patch_gerrit_url":     "https://" + g.host,
		"patch_issue":          g.issue,
		"patch_set":            g.patchset,
		"patch_project":        g.patchProject,
		"patch_ref":            g.patchRef,
		"patch_repository_url": g.repository,
		"repository":           g.repository,
		"patch_storage":        "gerrit",
		"blamelist":            []string{g.blame},
	}
}

func (g *gerritCL) loadRemoteData(ctx context.Context, authClient *http.Client) error {
	gc, err := gerrit.NewClient("https://"+g.host, authClient)
	if err != nil {
		return err
	}

	ci, _, err := gc.Changes.GetChangeDetail(strconv.FormatUint(g.issue, 10), &gerrit.ChangeOptions{
		AdditionalFields: []string{"ALL_REVISIONS", "DOWNLOAD_COMMANDS"}})
	if err != nil {
		return err
	}

	g.patchProject = ci.Project
	for commitID, rd := range ci.Revisions {
		if rd.Number == int(g.patchset) || (g.patchset == 0 && commitID == ci.CurrentRevision) {
			g.patchset = uint64(rd.Number)
			g.patchRef = rd.Ref
			g.repository = rd.Fetch["http"].URL
			g.blame = rd.Uploader.Email
			break
		}
	}

	return nil
}

type rietveldCL struct {
	// rietveld == https://host
	host string

	// issue == str(issue)
	issue uint64

	// patchset == str(patchset)
	patchset uint64

	// patch_project
	project string

	// blamelist == [blame]
	blame string
}

func (r *rietveldCL) getProperties() map[string]interface{} {
	return map[string]interface{}{
		"rietveld":      "https://" + r.host,
		"issue":         strconv.FormatUint(r.issue, 10),
		"patchset":      strconv.FormatUint(r.patchset, 10),
		"patch_project": r.project,
		"blamelist":     []string{r.blame},
		"patch_storage": "rietveld",
	}
}

func (r *rietveldCL) loadRemoteData(ctx context.Context, authClient *http.Client) error {
	rsp, err := authClient.Get(fmt.Sprintf("https://%s/api/%d", r.host, r.issue))
	if err != nil {
		return err
	}
	defer rsp.Body.Close()

	type rietveldDetail struct {
		OwnerEmail string   `json:"owner_email"`
		Project    string   `json:"project"`
		Patchsets  []uint64 `json:"patchsets"`
	}
	detail := &rietveldDetail{}
	if err := json.NewDecoder(rsp.Body).Decode(detail); err != nil {
		return err
	}
	r.project = detail.Project
	r.blame = detail.OwnerEmail
	if r.patchset == 0 {
		if len(detail.Patchsets) == 0 {
			return errors.New("rietveld patchset not specified and CL has no patchsets")
		}
		r.patchset = detail.Patchsets[len(detail.Patchsets)-1]
	}

	return nil
}

type cl interface {
	loadRemoteData(ctx context.Context, authClient *http.Client) error
	getProperties() map[string]interface{}
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
	ret = &gerritCL{host: p.Host}
	switch len(toks) {
	case 2:
		if ret.patchset, err = strconv.ParseUint(toks[1], 10, 0); err != nil {
			return
		}
		fallthrough
	case 1:
		ret.issue, err = strconv.ParseUint(toks[0], 10, 0)
	default:
		err = errors.New("unrecognized URL")
	}
	return
}

func parseRietveldURL(p *url.URL) (ret *rietveldCL, err error) {
	ret = &rietveldCL{host: p.Host}
	toks := urlTrimSplit(p.Path)
	if len(toks) < 1 {
		err = errors.Reason("len(path segments) < 1; %q", p.Path).Err()
		return
	}

	ret.issue, err = strconv.ParseUint(toks[0], 10, 0)
	if err != nil {
		err = errors.Annotate(err, "issue is not a number: %q", p.Path).Err()
		return
	}

	if p.Fragment == "" {
		return
	}
	if !strings.HasPrefix(p.Fragment, "ps") {
		err = errors.Reason("URL has #fagment, but doesn't start with `ps`: %q", p.Fragment).Err()
		return
	}

	_, err = fmt.Sscanf(p.Fragment, "ps%d", &ret.patchset)
	err = errors.Annotate(err, "parsing patchset url #fragment").Err()
	return
}

func parseCrChangeListURL(clURL string) (cl, error) {
	p, err := url.Parse(clURL)
	if err != nil {
		err = errors.Annotate(err, "URL_TO_CHANGELIST is invalid").Err()
		return nil, err
	}
	toks := urlTrimSplit(p.Path)
	if len(toks) == 0 || toks[0] == "c" {
		if len(toks) == 0 {
			// https://<gerrit_host>/#/c/<issue>
			// https://<gerrit_host>/#/c/<issue>/<patchset>
			toks = urlTrimSplit(p.Fragment)
			if len(toks) < 1 || toks[0] != "c" {
				return nil, errors.Reason("bad format for (old) gerrit URL: %q", clURL).Err()
			}
			toks = toks[1:] // remove "c"
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

	// https://<rietveld_host>/<issue>
	// https://<rietveld_host>/<issue>/#ps<patchset>
	ret, err := parseRietveldURL(p)
	err = errors.Annotate(err, "bad format for rietveld URL: %q", clURL).Err()
	return ret, err
}

// ChromiumCL edits the chromium-recipe-specific properties pertaining to
// a "tryjob" CL. These properties include things like "patch_storage", "issue",
// "rietveld", etc.
func (ejd *EditJobDefinition) ChromiumCL(ctx context.Context, authClient *http.Client, patchsetURL string) {
	if patchsetURL == "" {
		return
	}
	ejd.tweakUserland(func(u *Userland) error {
		// parse patchsetURL to see if we understand it
		clImpl, err := parseCrChangeListURL(patchsetURL)
		if err != nil {
			return err
		}

		// make some RPCs to the underlying service to extract the rest of the
		// properties.
		if err := clImpl.loadRemoteData(ctx, authClient); err != nil {
			return err
		}

		// wipe out all the old properties
		toDel := []string{
			"blamelist", "issue", "patch_gerrit_url", "patch_issue", "patch_project",
			"patch_ref", "patch_repository_url", "patch_set", "patch_storage",
			"patchset", "repository", "rietveld",
		}
		for _, key := range toDel {
			delete(u.RecipeProperties, key)
		}

		// set the properties.
		for k, v := range clImpl.getProperties() {
			u.RecipeProperties[k] = v
		}

		return nil
	})
}
