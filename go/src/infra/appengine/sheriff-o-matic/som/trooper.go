// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package som implements HTTP server that handles requests to default module.
package som

import (
	"encoding/json"

	"infra/monitoring/messages"

	"golang.org/x/net/context"

	"github.com/luci/gae/service/datastore"
)

// TrooperAlert ... Extended alert struct type for use in the trooper tab.
type TrooperAlert struct {
	messages.Alert
	Tree string `json:"tree"`
}

func getTrooperAlerts(c context.Context) ([]byte, error) {
	q := datastore.NewQuery("Tree")
	trees := []*Tree{}
	datastore.GetAll(c, q, &trees)

	result := make(map[string]interface{})
	alerts := []*TrooperAlert{}

	for _, t := range trees {
		q := datastore.NewQuery("AlertsJSON")
		q = q.Ancestor(datastore.MakeKey(c, "Tree", t.Name))
		q = q.Order("-Date")
		q = q.Limit(1)

		alertsJSON := []*AlertsJSON{}
		err := datastore.GetAll(c, q, &alertsJSON)
		if err != nil {
			return nil, err
		}

		if len(alertsJSON) > 0 {
			data := alertsJSON[0].Contents

			alertsSummary := &messages.AlertsSummary{}

			result["timestamp"] = alertsSummary.Timestamp
			result["revision_summaries"] = alertsSummary.RevisionSummaries
			result["date"] = alertsJSON[0].Date

			err = json.Unmarshal(data, alertsSummary)
			if err != nil {
				return nil, err
			}

			for _, a := range alertsSummary.Alerts {
				if a.Type == messages.AlertInfraFailure {
					newAlert := &TrooperAlert{a, t.Name}
					alerts = append(alerts, newAlert)
				}
			}
		}
	}

	result["alerts"] = alerts

	out, err := json.Marshal(result)

	if err != nil {
		return nil, err
	}

	return out, nil
}
