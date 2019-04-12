// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package afedb provides a client to query Autotest Front End database.
package afedb

import (
	"database/sql"
	"fmt"

	// mysql provides a database/sql driver but should not be directly
	// referenced.
	_ "github.com/go-sql-driver/mysql"
	"go.chromium.org/luci/common/data/stringset"
	"go.chromium.org/luci/common/data/strpair"
	"go.chromium.org/luci/common/errors"
)

// Client provides methods to query AFE database.
type Client struct {
	db *sql.DB
}

// DUT contains inventory information about a DUT obtained from the AFE.
type DUT struct {
	Hostname   string
	Labels     stringset.Set
	Attributes strpair.Map
}

// NewClient creates a new Client.
//
// On success, callers must defer client.Close() to release resources.
func NewClient(host, port, user, password string) (*Client, error) {
	dsn := fmt.Sprintf("%s:%s@tcp(%s:%s)/chromeos_autotest_db", user, password, host, port)
	db, err := sql.Open("mysql", dsn)
	if err != nil {
		return nil, errors.Annotate(err, "new afedb client").Err()
	}
	if err := db.Ping(); err != nil {
		_ = db.Close()
		return nil, errors.Annotate(err, "new afedb client").Err()
	}
	return &Client{db}, nil
}

// Close releases resources held by the Client.
func (c *Client) Close() error {
	return c.db.Close()
}

// QueryDUTs queries DUT information from the AFE.
//
// This function returns a map from DUT hostname to the associated DUTInfo.
func (c *Client) QueryDUTs() (map[string]*DUT, error) {
	dls, err := c.queryDUTLabels()
	if err != nil {
		return nil, errors.Annotate(err, "query DUTs").Err()
	}
	dattrs, err := c.queryDUTAttributes()
	if err != nil {
		return nil, errors.Annotate(err, "query DUTs").Err()
	}
	duts := make(map[string]*DUT)
	for h, ls := range dls {
		duts[h] = &DUT{
			Hostname:   h,
			Labels:     ls,
			Attributes: make(strpair.Map),
		}
	}
	for h, attrs := range dattrs {
		if d, ok := duts[h]; ok {
			d.Attributes = attrs
		} else {
			duts[h] = &DUT{
				Hostname:   h,
				Labels:     make(stringset.Set),
				Attributes: attrs,
			}
		}
	}
	return duts, nil
}

// queryDUTLabels queries DUTs and associated labels from the AFE.
//
// This function returns a map from DUT hostname to its labels.
func (c *Client) queryDUTLabels() (map[string]stringset.Set, error) {
	rows, err := c.db.Query(dutLabelsQuery)
	if err != nil {
		return nil, errors.Annotate(err, "query DUT labels").Err()
	}

	dl := make(map[string]stringset.Set)
	defer rows.Close()
	for rows.Next() {
		var h, v string
		err := rows.Scan(&h, &v)
		if err != nil {
			return nil, errors.Annotate(err, "query DUT labels").Err()
		}
		if _, ok := dl[h]; !ok {
			dl[h] = make(stringset.Set)
		}
		dl[h].Add(v)
	}
	return dl, nil
}

func (c *Client) queryDUTAttributes() (map[string]strpair.Map, error) {
	rows, err := c.db.Query(dutAttributesQuery)
	if err != nil {
		return nil, errors.Annotate(err, "query DUT attributes").Err()
	}

	attrs := make(map[string]strpair.Map)
	defer rows.Close()
	for rows.Next() {
		var h, k, v string
		err := rows.Scan(&h, &k, &v)
		if err != nil {
			return nil, errors.Annotate(err, "query DUT labels").Err()
		}
		if _, ok := attrs[h]; !ok {
			attrs[h] = make(strpair.Map)
		}
		attrs[h].Add(k, v)
	}
	return attrs, nil
}

const (
	dutLabelsQuery = `
	SELECT afe_hosts.hostname, afe_labels.name
        FROM afe_hosts JOIN afe_hosts_labels JOIN afe_labels
        ON (afe_hosts.id = afe_hosts_labels.host_id AND
            afe_hosts_labels.label_id = afe_labels.id)
        WHERE afe_labels.invalid = 0
        ORDER BY afe_hosts.hostname;
  `
	dutAttributesQuery = `
          SELECT afe_hosts.hostname, afe_host_attributes.attribute,
            afe_host_attributes.value
          FROM afe_hosts JOIN afe_host_attributes
          ON (afe_hosts.id = afe_host_attributes.host_id)
          ORDER BY afe_host_attributes.attribute;
	`
)
