// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package buildextract contains structs useful in deserializing json data from
// CBE, e.g. https://chrome-build-extract.appspot.com/get_master/chromium

package messages

// BuildExtract is AKA "master_data" from builder_alerts.py.
type BuildExtract struct {
	AcceptingBuilds  AcceptingBuilds        `json:"accepting_builds"`
	Builders         map[string]Builders    `json:"builders"`
	Buildstate       Buildstate             `json:"buildstate"`
	Changes          map[string]Changes     `json:"changes"`
	Clock            Clock                  `json:"clock"`
	Created          string                 `json:"created"`
	CreatedTimestamp EpochTime              `json:"created_timestamp"`
	Metrics          map[string]interface{} `json:"metrics"`
	Project          Project                `json:"project"`
	Slaves           map[string]Slaves      `json:"slaves"`
}

// Builder represents a buildbot builder's state.
type Builder struct {
	Builds []Builds `json:"builds"`
	Cursor string   `json:"cursor"`
}

// Builds represents a buildbot build.
type Builds struct {
	Blame            []string  `json:"blame"`
	BuilderName      string    `json:"builderName"`
	CreatedTimestamp EpochTime `json:"created_timestamp"`
	CurrentStep      `json:"currentStep"`
	Eta              EpochTime       `json:"eta"`
	Logs             [][]string      `json:"logs"`
	Number           int64           `json:"number"`
	Properties       [][]interface{} `json:"properties"`
	Reason           string          `json:"reason"`
	Results          int64           `json:"results"`
	Slave            string          `json:"slave"`
	SourceStamp      SourceStamp     `json:"sourceStamp"`
	Steps            []Steps         `json:"steps"`
	Text             []string        `json:"text"`
	Times            []EpochTime     `json:"times"`
}

// Slaves is an automatically generated type.
type Slaves struct {
	//	AccessUri	map[string]interface{}	`json:"access_uri"`
	//	Admin	map[string]interface{}	`json:"admin"`
	Builders      map[string][]float64 `json:"builders"`
	Connected     bool                 `json:"connected"`
	Host          string               `json:"host"`
	Name          string               `json:"name"`
	RunningBuilds []Builds             `json:"runningBuilds"`
	Version       string               `json:"version"`
}

// Builders is an automatically generated type.
type Builders struct {
	Basedir       string   `json:"basedir"`
	BuildState    URLs     `json:"buildState"`
	BuilderName   string   `json:"builderName"`
	CachedBuilds  []int64  `json:"cachedBuilds"`
	Category      string   `json:"category"`
	CurrentBuilds []int64  `json:"currentBuilds"`
	PendingBuilds float64  `json:"pendingBuilds"`
	Slaves        []string `json:"slaves"`
	State         string   `json:"state"`
}

// Project is an automatically generated type.
type Project struct {
	BuildbotURL string `json:"buildbotURL"`
	Title       string `json:"title"`
	TitleURL    string `json:"titleURL"`
}

// CurrentStep is an automatically generated type.
type CurrentStep struct {
	Eta          EpochTime       `json:"eta"`
	Expectations [][]interface{} `json:"expectations"`
	Hidden       bool            `json:"hidden"`
	IsFinished   bool            `json:"isFinished"`
	IsStarted    bool            `json:"isStarted"`
	Logs         [][]interface{} `json:"logs"`
	Name         string          `json:"name"`
	Statistics   URLs            `json:"statistics"`
	StepNumber   float64         `json:"step_number"`
	Text         []string        `json:"text"`
	Times        []float64       `json:"times"`
	URLs         URLs            `json:"urls"`
}

// Changes is an automatically generated type.
type Changes struct {
	At         string          `json:"at"`
	Branch     string          `json:"branch"`
	Category   string          `json:"category"`
	Comments   string          `json:"comments"`
	Files      []Files         `json:"files"`
	Number     float64         `json:"number"`
	Project    string          `json:"project"`
	Properties [][]interface{} `json:"properties"`
	Repository string          `json:"repository"`
	Rev        string          `json:"rev"`
	Revision   string          `json:"revision"`
	Revlink    string          `json:"revlink"`
	When       EpochTime       `json:"when"`
	Who        string          `json:"who"`
}

// ChangeSources is an automatically generated type.
type ChangeSources struct {
	Description string `json:"description"`
}

// AcceptingBuilds is an automatically generated type.
type AcceptingBuilds struct {
	AcceptingBuilds bool `json:"accepting_builds"`
}

// Buildstate is an automatically generated type.
type Buildstate struct {
	AcceptingBuilds bool       `json:"accepting_builds"`
	Builders        []Builders `json:"builders"`
	Project         Project    `json:"project"`
	Timestamp       EpochTime  `json:"timestamp"`
}

// Current is an automatically generated type.
type Current struct {
	Local string    `json:"local"`
	Utc   string    `json:"utc"`
	UtcTs EpochTime `json:"utc_ts"`
}

// Clock is an automatically generated type.
type Clock struct {
	Current       Current   `json:"current"`
	ServerStarted Current   `json:"server_started"`
	ServerUptime  EpochTime `json:"server_uptime"`
}

// URLs is an automatically generated type.
type URLs struct {
}

// Steps is an automatically generated type.
type Steps struct {
	Eta          EpochTime       `json:"eta"`
	Expectations [][]interface{} `json:"expectations"`
	Hidden       bool            `json:"hidden"`
	IsFinished   bool            `json:"isFinished"`
	IsStarted    bool            `json:"isStarted"`
	Logs         [][]interface{} `json:"logs"`
	Name         string          `json:"name"`
	// Results is a homogenous array. Use runtime introspection to
	// determine element types.
	Results    []interface{} `json:"results"`
	Statistics URLs          `json:"statistics"`
	StepNumber float64       `json:"step_number"`
	Text       []string      `json:"text"`
	Times      []float64     `json:"times"`
	URLs       URLs          `json:"urls"`
}

// Files is an automatically generated type.
type Files struct {
	Name string                 `json:"name"`
	URL  map[string]interface{} `json:"url"`
}

// SourceStamp is an automatically generated type.
type SourceStamp struct {
	Branch     string    `json:"branch"`
	Changes    []Changes `json:"changes"`
	HasPatch   bool      `json:"hasPatch"`
	Project    string    `json:"project"`
	Repository string    `json:"repository"`
	Revision   string    `json:"revision"`
}
