// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package handler

import (
	"fmt"
	"strings"

	"infra/appengine/sheriff-o-matic/som/model"

	"golang.org/x/net/context"

	"go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/server/settings"
)

// SettingsUIPage is the SoM admin settings page.
type SettingsUIPage struct {
	settings.BaseUIPage
}

// Title returns the settings page title.
func (SettingsUIPage) Title(c context.Context) (string, error) {
	return "Admin SOM settings", nil
}

// Fields returns a list of settings fields.
func (SettingsUIPage) Fields(c context.Context) ([]settings.UIField, error) {
	fields := []settings.UIField{
		{
			ID:    "Trees",
			Title: "Trees in SOM",
			Type:  settings.UIFieldText,
			Help:  "Trees listed in SOM. Comma separated values. treeA,treeB",
		},
		{
			ID:    "BugQueueLabels",
			Title: "Bug Queue Labels",
			Type:  settings.UIFieldText,
			Help:  "Bug queue label for each tree. treeA:queueA,treeB:queueB",
		},
	}

	q := datastore.NewQuery("Tree")
	trees := []*model.Tree{}
	datastore.GetAll(c, q, &trees)

	// Add settings fields for specific trees
	for _, t := range trees {
		fields = append(fields, settings.UIField{
			ID:    fmt.Sprintf("AlertStreams-%s", t.Name),
			Title: fmt.Sprintf("%s Alert Streams", t.DisplayName),
			Type:  settings.UIFieldText,
			Help:  "Alert streams for this tree. Defaults to tree name if blank. streamA,streamB",
		})
		fields = append(fields, settings.UIField{
			ID:    fmt.Sprintf("HelpLink-%s", t.Name),
			Title: fmt.Sprintf("%s Help Link", t.DisplayName),
			Type:  settings.UIFieldText,
			Help:  "A link to help documentation for this tree. ie. a playbook",
		})
		fields = append(fields, settings.UIField{
			ID:    fmt.Sprintf("GerritProject-%s", t.Name),
			Title: fmt.Sprintf("%s Gerrit Project", t.DisplayName),
			Type:  settings.UIFieldText,
			Help:  "The Gerrit project for this tree.",
		})
		fields = append(fields, settings.UIField{
			ID:    fmt.Sprintf("GerritInstance-%s", t.Name),
			Title: fmt.Sprintf("%s Gerrit Instance", t.DisplayName),
			Type:  settings.UIFieldText,
			Help:  "The Gerrit instance for this tree.",
		})
	}

	return fields, nil
}

// ReadSettings converts query paramters and POST body into settings values.
func (SettingsUIPage) ReadSettings(c context.Context) (map[string]string, error) {
	q := datastore.NewQuery("Tree")
	results := []*model.Tree{}
	datastore.GetAll(c, q, &results)
	trees := make([]string, len(results))
	queues := make([]string, len(results))

	values := make(map[string]string)

	for i, t := range results {
		trees[i] = fmt.Sprintf("%s:%s", t.Name, t.DisplayName)
		queues[i] = fmt.Sprintf("%s:%s", t.Name, t.BugQueueLabel)

		values[fmt.Sprintf("AlertStreams-%s", t.Name)] = strings.Join(t.AlertStreams, ",")
		values[fmt.Sprintf("HelpLink-%s", t.Name)] = t.HelpLink
		values[fmt.Sprintf("GerritProject-%s", t.Name)] = t.GerritProject
		values[fmt.Sprintf("GerritInstance-%s", t.Name)] = t.GerritInstance
	}

	values["Trees"] = strings.Join(trees, ",")
	values["BugQueueLabels"] = strings.Join(queues, ",")

	return values, nil
}

func deleteAllTrees(c context.Context) error {
	q := datastore.NewQuery("Tree")
	trees := []*model.Tree{}
	err := datastore.GetAll(c, q, &trees)
	if err != nil {
		return err
	}

	err = datastore.Delete(c, trees)

	if err != nil {
		return err
	}
	return nil
}

func initializeTrees(c context.Context, treeStr string) ([]*model.Tree, error) {
	toMake := strings.Split(treeStr, ",")
	trees := make([]*model.Tree, len(toMake))
	for i, it := range toMake {
		it = strings.TrimSpace(it)
		if len(it) == 0 {
			continue
		}

		nameParts := strings.Split(it, ":")
		name := nameParts[0]
		displayName := strings.Replace(strings.Title(name), "_", " ", -1)
		if len(nameParts) == 2 {
			displayName = nameParts[1]
		}
		trees[i] = &model.Tree{
			Name:        name,
			DisplayName: displayName,
		}
	}
	return trees, nil
}

// bugQueueLabels format is treeA:queueA,treeB:queueB
func splitBugQueueLabels(c context.Context, bugQueueLabels string) (map[string]string, error) {
	result := make(map[string]string)
	queueLabels := strings.Split(bugQueueLabels, ",")
	for _, label := range queueLabels {
		split := strings.Split(label, ":")
		if len(split) != 2 {
			return nil, fmt.Errorf("invalid bugQueueLabels: %q", bugQueueLabels)
		}
		result[split[0]] = split[1]
	}

	return result, nil
}

func writeAllValues(c context.Context, values map[string]string) error {
	trees := []*model.Tree{}
	if treeStr, ok := values["Trees"]; ok {
		// Always replace the existing list of trees. Otherwise there's no "delete"
		// capability.
		err := deleteAllTrees(c)
		if err != nil {
			return err
		}

		trees, err = initializeTrees(c, treeStr)
		if err != nil {
			return err
		}
	} else {
		q := datastore.NewQuery("Tree")
		trees = []*model.Tree{}
		datastore.GetAll(c, q, &trees)
	}

	labels := make(map[string]string)
	if bugQueueLabels, ok := values["BugQueueLabels"]; ok && bugQueueLabels != "" {
		// Split the bug queue labels first and write later to help minimize writes
		l, err := splitBugQueueLabels(c, bugQueueLabels)
		if err != nil {
			return err
		}
		labels = l
	}

	for _, t := range trees {
		if bugQueueLabel, ok := labels[t.Name]; ok {
			t.BugQueueLabel = bugQueueLabel
		}

		if alertStreams, ok := values[fmt.Sprintf("AlertStreams-%s", t.Name)]; ok {
			if alertStreams != "" {
				t.AlertStreams = strings.Split(alertStreams, ",")
			} else {
				t.AlertStreams = []string(nil)
			}
		}

		if helpLink, ok := values[fmt.Sprintf("HelpLink-%s", t.Name)]; ok {
			t.HelpLink = helpLink
		}

		if gerritProject, ok := values[fmt.Sprintf("GerritProject-%s", t.Name)]; ok {
			t.GerritProject = gerritProject
		}

		if gerritInstance, ok := values[fmt.Sprintf("GerritInstance-%s", t.Name)]; ok {
			t.GerritInstance = gerritInstance
		}

		// Try to do only write per tree each save.
		if err := datastore.Put(c, t); err != nil {
			return err
		}
	}
	return nil
}

// WriteSettings persists the settings values.
func (SettingsUIPage) WriteSettings(c context.Context, values map[string]string, who, why string) error {
	// Putting the write logic in a function outside of WriteSettings makes unit testing easier.
	return writeAllValues(c, values)
}
