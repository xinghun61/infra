// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package dashboard

import (
	"html/template"
	"net/http"
	"time"
)

const (
	// RED is the constant to represent paging alerts.
	RED = 1
	// YELLOW is the constant to represent email alerts.
	YELLOW = 2
)

// ChopsService represents a service that has an SLA.
type ChopsService struct {
	Name      string
	SLA       string
	Incidents []Incident
}

// NonSLAService represents a service that does not have an SLA yet.
type NonSLAService struct {
	Name      string
	Incidents []Incident
}

// Incident represents a service disruption or outage incident.
type Incident struct {
	ID        int
	Open      bool
	StartTime string
	EndTime   string
	Severity  int
}

// PageData contains information needed by the template.
type PageData struct {
	ChopsServices  []ChopsService
	NonSLAServices []NonSLAService
	Dates          []string
}

var templates = template.Must(template.ParseGlob("templates/*"))

func init() {
	http.HandleFunc("/", dashboard)
}

func dashboard(w http.ResponseWriter, r *http.Request) {

	dates := make([]string, 7)
	for i := 0; i < 7; i++ {
		dates[i] = time.Now().AddDate(0, 0, -i).Format("01/02/2006")
	}
	services, nonSLAServices := makeFakeData()
	pageData := PageData{
		ChopsServices:  services,
		NonSLAServices: nonSLAServices,
		Dates:          dates,
	}

	if err := templates.ExecuteTemplate(
		w, "dash_template.html", pageData); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
	}
}

func makeFakeData() (services []ChopsService, nonSLAServices []NonSLAService) {

	incidents := []Incident{
		{
			ID:        1,
			Open:      false,
			StartTime: "03/17/2017",
			EndTime:   "03/18/2017",
			Severity:  RED,
		},
		{
			ID:        2,
			Open:      false,
			StartTime: "03/19/2017",
			EndTime:   "03/19/2017",
			Severity:  YELLOW,
		},
		{
			ID:        3,
			Open:      true,
			StartTime: "03/20/2017",
			EndTime:   "",
			Severity:  RED,
		},
	}

	services = []ChopsService{
		{
			Name:      "Monorail",
			SLA:       "http://www.google.com",
			Incidents: incidents,
		},
		{
			Name:      "Sheriff-O-Matic",
			SLA:       "http://www.google.com",
			Incidents: incidents,
		},
	}

	nonSLAServices = []NonSLAService{
		{Name: "Commit Queue", Incidents: incidents},
		{Name: "Code Search", Incidents: incidents},
	}

	return
}
