// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package frontend

import (
	"encoding/json"
	"fmt"
	"net/http"
	"sync"

	"go.chromium.org/gae/service/urlfetch"
	"go.chromium.org/luci/server/router"
)

// TODO(estaab): Comment copied from python implementation:
//   Get rid of this one crrev.com supports this directly.
//   See http://crbug.com/407198.

// crRevURL is the base URL of the Chromium Revision's API.
var crRevURL = "https://cr-rev.appspot.com/_ah/api/crrev/v1/redirect"

type crRevClient struct {
	HTTPClient *http.Client
	BaseURL    string
}

// commitHash returns the commit hash for the supplied commit
// position.
func (c *crRevClient) commitHash(pos string) (string, error) {
	resp, err := c.HTTPClient.Get(c.BaseURL + "/" + pos)
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return "", fmt.Errorf("HTTP status code %d from %s", resp.StatusCode, resp.Request.URL)
	}

	hash := struct {
		Hash string `json:"git_sha"`
	}{}
	if err := json.NewDecoder(resp.Body).Decode(&hash); err != nil {
		return "", err
	}
	return hash.Hash, nil
}

func revisionHandler(c *router.Context) {
	client := crRevClient{
		HTTPClient: &http.Client{Transport: urlfetch.Get(c.Context)},
		BaseURL:    crRevURL,
	}
	type result struct {
		hash string
		err  error
	}
	results := make([]result, 2)
	wg := sync.WaitGroup{}
	wg.Add(2)

	go func() {
		defer wg.Done()
		hash, err := client.commitHash(c.Request.FormValue("start"))
		results[0] = result{hash, err}
	}()
	go func() {
		defer wg.Done()
		hash, err := client.commitHash(c.Request.FormValue("end"))
		results[1] = result{hash, err}
	}()

	wg.Wait()
	for _, r := range results {
		if r.err != nil {
			http.Error(c.Writer, r.err.Error(), http.StatusInternalServerError)
			return
		}
	}

	redirectURL := fmt.Sprintf(
		"https://chromium.googlesource.com/chromium/src/+log/%s^..%s?pretty=fuller&n=%s",
		results[0].hash, results[1].hash, c.Request.FormValue("n"))
	http.Redirect(c.Writer, c.Request, redirectURL, http.StatusMovedPermanently)
}
