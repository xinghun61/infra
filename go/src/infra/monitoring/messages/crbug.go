// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package messages

// CrbugSearchResults conatains issue search results from crbug.
type CrbugSearchResults struct {
	Items        []CrbugItem `json:"items"`
	Kind         string      `json:"kind"`
	TotalResults float64     `json:"totalResults"`
}

// CrbugAuthor is the author of an issue.
type CrbugAuthor struct {
	HtmlLink string `json:"htmlLink"`
	Kind     string `json:"kind"`
	Name     string `json:"name"`
}

// CrbugItem represents an issue in crbug.
type CrbugItem struct {
	Author     CrbugAuthor `json:"author"`
	CanComment bool        `json:"canComment"`
	CanEdit    bool        `json:"canEdit"`
	Id         float64     `json:"id"`
	Kind       string      `json:"kind"`
	Labels     []string    `json:"labels"`
	ProjectId  string      `json:"projectId"`
	Published  string      `json:"published"`
	Starred    bool        `json:"starred"`
	Stars      float64     `json:"stars"`
	State      string      `json:"state"`
	Status     string      `json:"status"`
	Summary    string      `json:"summary"`
	Title      string      `json:"title"`
	Updated    string      `json:"updated"`
}
