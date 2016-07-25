// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package common implements common functionality for the Tricium service modules.
package common

import (
	"fmt"
	"html/template"
	"net/http"
)

var basePage = template.Must(template.ParseFiles("templates/base.html"))

// ShowBasePage executes the base page template
func ShowBasePage(w http.ResponseWriter, d interface{}) {
	executeTemplate(basePage, w, d)
}

func executeTemplate(t *template.Template, w http.ResponseWriter, d interface{}) error {
	if err := t.Execute(w, d); err != nil {
		http.Error(w, "Internal server error. We are working on it.", http.StatusInternalServerError)
		return fmt.Errorf("error executing template: %v", err)
	}
	return nil
}
