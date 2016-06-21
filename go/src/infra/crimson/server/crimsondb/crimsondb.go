// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package crimsondb

import (
	"bytes"
	"database/sql"
	"encoding/hex"
	"fmt"
	"net"

	"github.com/luci/luci-go/common/logging"
	"golang.org/x/net/context"

	// This simply registers the mysql driver.
	_ "github.com/go-sql-driver/mysql"

	"infra/crimson/proto"
)

// IPRangeRow describes a row in the ip_range table.
type IPRangeRow struct {
	Site    string
	Vlan    string
	StartIP string
	EndIP   string
}

func (row IPRangeRow) String() string {
	return fmt.Sprintf("%s/%s: %s-%s",
		row.Site, row.Vlan, row.StartIP, row.EndIP)
}

// IPStringToHexString converts an IP address into a hex string suitable for MySQL.
func IPStringToHexString(ip string) (string, error) {
	ipb := net.ParseIP(ip)
	if ipb == nil {
		return "", fmt.Errorf("parsing of IP address failed: %s", ip)
	}
	if ipb.DefaultMask() != nil {
		ipb = ipb.To4()
	}
	return "0x" + hex.EncodeToString(ipb), nil
}

// HexStringToIP converts an hex string returned by MySQL into a net.IP structure.
func HexStringToIP(hexIP string) net.IP {
	// TODO(pgervais): Add decent error checking. Ex: check hexIP starts with '0x'.
	ip, _ := hex.DecodeString(hexIP[2:])
	length := 4
	if len(ip) > 4 {
		length = 16
	}
	netIP := make(net.IP, length)
	for n := 1; n <= len(ip); n++ {
		netIP[length-n] = ip[len(ip)-n]
	}
	return netIP
}

// InsertIPRange adds a new IP range in the corresponding table.
func InsertIPRange(ctx context.Context, row *crimson.IPRange) error {
	db := ctx.Value("dbHandle").(*sql.DB)

	if len(row.Site) == 0 {
		logging.Errorf(ctx, "Received empty site value.")
		return fmt.Errorf("Received empty site value.")
	}

	var err error
	var startIP, endIP string
	startIP, err = IPStringToHexString(row.StartIp)
	if err != nil {
		return err
	}
	endIP, err = IPStringToHexString(row.EndIp)
	if err != nil {
		return err
	}

	statement := ("INSERT INTO ip_range (site, vlan, start_ip, end_ip)\n" +
		"VALUES (?, ?, ?, ?)")
	_, err = db.Exec(statement,
		row.Site,
		row.Vlan,
		startIP,
		endIP)
	if err != nil {
		logging.Errorf(ctx, "IP range insertion failed. %s", err)
	}
	return err
}

// SelectIPRange returns ip ranges filtered by values in req.
func SelectIPRange(ctx context.Context, req *crimson.IPRangeQuery) []IPRangeRow {
	db := ctx.Value("dbHandle").(*sql.DB)
	var rows *sql.Rows
	var err error

	vlan := req.Vlan
	site := req.Site

	statement := bytes.Buffer{}
	params := []interface{}{}

	statement.WriteString("SELECT vlan, site, start_ip, end_ip FROM ip_range")

	if site != "" || vlan != "" {
		statement.WriteString("\nWHERE ")
	}

	if site != "" {
		statement.WriteString("site=?")
		params = append(params, site)
	}

	if vlan != "" {
		if site != "" {
			statement.WriteString("\nAND ")
		}
		statement.WriteString("vlan=?")
		params = append(params, vlan)
	}

	if req.Limit > 0 {
		statement.WriteString("\nLIMIT ?")
		params = append(params, req.Limit)
	}

	rows, err = db.Query(statement.String(), params...)

	if err != nil {
		// TODO(pgervais): propagate the error up the stack.
		logging.Errorf(ctx, "%s", err)
		return []IPRangeRow{}
	}

	var ipRanges []IPRangeRow

	for rows.Next() {
		var startIP, endIP string
		ipRange := IPRangeRow{}
		err := rows.Scan(
			&ipRange.Vlan, &ipRange.Site, &startIP, &endIP)
		if err != nil {
			logging.Errorf(ctx, "%s", err)
			return []IPRangeRow{}
		}
		ipRange.StartIP = HexStringToIP(startIP).String()
		ipRange.EndIP = HexStringToIP(endIP).String()
		ipRanges = append(ipRanges, ipRange)
	}
	err = rows.Err()
	if err != nil {
		logging.Errorf(ctx, "%s", err)
		return []IPRangeRow{}
	}
	return ipRanges
}

// GetDBHandle returns a handle to the Cloud SQL instance used by this deployment.
func GetDBHandle() (*sql.DB, error) {
	// TODO(pgervais): do not hard-code the name of the database.
	return sql.Open("mysql", "root@cloudsql(crimson-staging:crimson-staging)/crimson")
}
