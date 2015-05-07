// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package client

import (
	"encoding/json"
	"fmt"
	"io/ioutil"
	"net/http"
	"net/url"
	"strings"
	"sync/atomic"

	"github.com/Sirupsen/logrus"

	"infra/monitoring/messages"
)

var (
	log = logrus.New()
)

// Client provides access to read status information from various parts of chrome
// developer infrastructure.
type Client interface {
	// Build fetches the build summary for master mn, builder bn and build id bID
	// from build.chromium.org.
	Build(mn, bn string, bID int64) (*messages.Build, error)

	// TestResults fetches the results of a step failure's test run.
	TestResults(masterName, builderName, stepName string, buildNumber int64) (*messages.TestResults, error)

	// BuildExtracts fetches build information for masters from CBE in parallel.
	// Returns a map of url to error for any requests that had errors.
	BuildExtracts(urls []string) (map[string]*messages.BuildExtract, map[string]error)

	// StdioForStep fetches the standard output for a given build step, and an error if any
	// occurred.
	StdioForStep(master, builder, step string, bID int64) ([]string, error)

	// JSON fetches data from a json endpoint and decodes it into v.  Returns the
	// http response code and error, if any.
	JSON(URL string, v interface{}) (int, error)

	// DumpStats logs stats about the client to stdout.
	DumpStats()
}

type client struct {
	hc *http.Client
	// Some counters for reporting. Only modify through synchronized methods.
	// TODO: add some more detailed stats about response times so we can
	// track and alert on those too.
	totalReqs  int64
	totalErrs  int64
	totalBytes int64
	currReqs   int64
}

// New returns a new Client.
func New() Client {
	return &client{hc: http.DefaultClient}
}

func (c *client) Build(mn, bn string, bID int64) (*messages.Build, error) {
	URL := fmt.Sprintf("https://build.chromium.org/p/%s/json/builders/%s/builds/%d",
		mn, bn, bID)

	bld := &messages.Build{}
	if code, err := c.JSON(URL, bld); err != nil {
		log.Errorf("Error (%d) fetching %s: %v", code, URL, err)
		return nil, err
	}

	return bld, nil
}

func (c *client) TestResults(masterName, builderName, stepName string, buildNumber int64) (*messages.TestResults, error) {
	// This substitution is done in the existing builder_alerts python code.
	if stepName == "webkit_tests" {
		stepName = "layout-tests"
	}

	v := url.Values{}
	v.Add("name", "full_results.json")
	v.Add("master", masterName)
	v.Add("builder", builderName)
	v.Add("buildnumber", fmt.Sprintf("%d", buildNumber))
	v.Add("testtype", stepName)

	URL := fmt.Sprintf("https://test-results.appspot.com/testfile?%s", v.Encode())
	tr := &messages.TestResults{}

	if code, err := c.JSON(URL, tr); err != nil {
		log.Errorf("Error (%d) fetching %s: %v", code, URL, err)
		return nil, err
	}

	return tr, nil
}

// It might make sense to add this to the Client interface, but none of the currently
// test-covered code paths depend on it.  Also, make this and the other funcs consistent on
// whether or not they do batch requests.  I think the existence of some data dependencies
// between responses and requests they generate makes this a hard choice.
func (c *client) BuildExtracts(urls []string) (map[string]*messages.BuildExtract, map[string]error) {
	type r struct {
		url string
		be  *messages.BuildExtract
		err error
	}

	ch := make(chan r, len(urls))

	for _, u := range urls {
		go func(url string) {
			out := r{url: url}
			defer func() {
				ch <- out
			}()

			out.be = &messages.BuildExtract{}
			_, out.err = c.JSON(url, out.be)
		}(u)
	}

	ret := map[string]*messages.BuildExtract{}
	errs := map[string]error{}
	for _ = range urls {
		r := <-ch
		if r.err != nil {
			errs[r.url] = r.err
		} else {
			ret[r.url] = r.be
		}
	}

	return ret, errs
}

func (c *client) StdioForStep(master, builder, step string, bID int64) ([]string, error) {
	URL := fmt.Sprintf("https://build.chromium.org/p/%s/builders/%s/builds/%d/steps/%s/logs/stdio/text", master, builder, bID, step)
	res, _, err := c.Text(URL)
	return strings.Split(res, "\n"), err
}

func (c *client) startReq() {
	atomic.AddInt64(&c.currReqs, 1)
	atomic.AddInt64(&c.totalReqs, 1)
}

func (c *client) endReq(r int64) {
	atomic.AddInt64(&c.currReqs, -1)
	atomic.AddInt64(&c.totalBytes, r)
}

func (c *client) errReq() {
	atomic.AddInt64(&c.currReqs, -1)
	atomic.AddInt64(&c.totalErrs, 1)
}

func (c *client) trackRequestStats(cb func() (int64, error)) error {
	var err error
	length := int64(0)
	c.startReq()
	defer func() {
		if err != nil {
			c.errReq()
		} else {
			c.endReq(length)
		}
	}()
	length, err = cb()
	return err
}

// JSON does a simple HTTP GET on a JSON endpoint.
//
// Returns the status code and the error, if any.
func (c *client) JSON(url string, v interface{}) (status int, err error) {
	err = c.trackRequestStats(func() (length int64, err error) {
		log.Infof("Fetching json (%d): %s", c.currReqs, url)
		resp, err := c.hc.Get(url)
		status = resp.StatusCode
		if err != nil {
			return
		}
		defer resp.Body.Close()
		if err = json.NewDecoder(resp.Body).Decode(v); err != nil {
			return
		}
		ct := strings.ToLower(resp.Header.Get("Content-Type"))
		expected := "application/json"
		if ct != expected {
			err = fmt.Errorf("unexpected Content-Type, expected \"%s\", got \"%s\": %s", expected, ct, url)
			return
		}
		if resp.StatusCode >= 400 {
			err = fmt.Errorf("http status %d: %s", resp.StatusCode, url)
			return
		}

		length = resp.ContentLength

		log.Infof("Fetched(%d) json: %s", resp.StatusCode, url)
		return length, err
	})

	return status, err
}

// Text does a simple HTTP GET on a text endpoint.
//
// Returns the status code and the error, if any.
func (c *client) Text(url string) (ret string, status int, err error) {
	err = c.trackRequestStats(func() (length int64, err error) {

		log.Infof("Fetching text (%d): %s", c.currReqs, url)
		resp, err := c.hc.Get(url)
		if err != nil {
			err = fmt.Errorf("couldn't resolve %s: %s", url, err)
			return
		}
		defer resp.Body.Close()

		b, err := ioutil.ReadAll(resp.Body)
		status = resp.StatusCode
		if err != nil {
			return
		}

		if resp.StatusCode >= 400 {
			err = fmt.Errorf("http status %d: %s", resp.StatusCode, url)
			return
		}

		ret = string(b)
		length = resp.ContentLength

		log.Infof("Fetched(%d) text: %s", resp.StatusCode, url)
		return length, err
	})
	return ret, status, nil
}

func (c *client) DumpStats() {
	log.Infof("%d reqs total, %d errors, %d current", c.totalReqs, c.totalErrs, c.currReqs)
	log.Infof("%d bytes read", c.totalBytes)
}
