// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package dashboard

import (
	"html/template"
	"net/http"
	"time"

	"github.com/luci/luci-go/common/logging"
	"google.golang.org/appengine"
)

const (
	// alertRed represents paging alerts.
	alertRed = 1
	// alertYellow represents email alerts.
	alertYellow = 2
)

// ChopsService represents a service that has an SLA.
type ChopsService struct {
	Name      string
	Sla       string
	Incidents []Incident
}

// NonSLAService represents a service that does not have an SLA yet.
type NonSLAService struct {
	Name      string
	Incidents []Incident
}

// Incident represents a service disruption or outage incident.
type Incident struct {
	Id        int
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
	ctx := appengine.NewContext(r)
	dates := []string{}
	for i := 0; i < 7; i++ {
		dates = append(dates, time.Now().AddDate(0, 0, -i).Format("01-02-2006"))
	}
	services, nonSLAServices := makeFakeData()
	pageData := PageData{
		ChopsServices:  services,
		NonSLAServices: nonSLAServices,
		Dates:          dates,
	}

	if err := templates.ExecuteTemplate(w, "dash.tmpl", pageData); err != nil {
		logging.Errorf(ctx, "while rendering dashboard: %s", err)
		return
	}
}

func makeFakeData() ([]ChopsService, []NonSLAService) {
	incidents := []Incident{
		{
			Id:        1,
			Open:      false,
			StartTime: "03-26-2017",
			EndTime:   "03-26-2017",
			Severity:  alertRed,
		},
		{
			Id:        2,
			Open:      false,
			StartTime: "03-25-2017",
			EndTime:   "03-25-2017",
			Severity:  alertYellow,
		},
		{
			Id:        3,
			Open:      true,
			StartTime: "03-28-2017",
			EndTime:   "",
			Severity:  alertRed,
		},
	}

	services := []ChopsService{
		{
			Name:      "Monorail",
			Sla:       "http://www.google.com",
			Incidents: incidents,
		},
		{
			Name:      "Sheriff-O-Matic",
			Sla:       "http://www.google.com",
			Incidents: incidents,
		},
	}

	nonSLAServices := []NonSLAService{
		{Name: "CommitQueue", Incidents: incidents},
		{Name: "CodeSearch", Incidents: incidents},
	}

	return services, nonSLAServices
}
