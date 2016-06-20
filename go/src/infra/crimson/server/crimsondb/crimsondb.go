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
	"strings"

	"github.com/luci/luci-go/common/logging"
	"golang.org/x/net/context"

	_ "github.com/go-sql-driver/mysql"

	"infra/crimson/proto"
)

type IPRangeRow struct {
	Site    string
	Vlan    string
	StartIp string
	EndIp   string
}

func (this IPRangeRow) String() string {
	return fmt.Sprintf("%s/%s: %s-%s",
		this.Site, this.Vlan, this.StartIp, this.EndIp)
}

// IPStringToHexString converts an IP address into a hex string suitable for MySQL.
func IPStringToHexString(ip string) string {
	ipb := net.ParseIP(ip)
	if ipb.DefaultMask() != nil {
		ipb = ipb.To4()
	}
	return "0x" + hex.EncodeToString(ipb)
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

func InsertIPRangeRows(ctx context.Context, rows []IPRangeRow) {
	db := ctx.Value("dbHandle").(*sql.DB)
	// TODO(pgervais): return the number of rows inserted (see row_count in mysql)

	values := make([]string, 0)
	for _, row := range rows {
		// FIXME(pgervais): THIS IS SUSCEPTIBLE TO SQL INJECTION.
		if row.StartIp != "" && row.EndIp != "" {
			values = append(values,
				fmt.Sprintf("('%s', '%s', '%s', '%s')",
					row.Site, row.Vlan,
					IPStringToHexString(row.StartIp),
					IPStringToHexString(row.EndIp)))
		}
	}
	if len(values) > 0 {
		statement := "insert into ip_range (site, vlan, start_ip, end_ip) values " +
			strings.Join(values, ",")
		_, err := db.Exec(statement)
		if err != nil {
			logging.Errorf(ctx, "IP range insertion failed. %s", err)
			return
		}
	} else {
		logging.Infof(ctx, "No IP range provided")
	}
}

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

	ipRanges := make([]IPRangeRow, 0)
	for rows.Next() {
		var startIp, endIp string
		ipRange := IPRangeRow{}
		err := rows.Scan(
			&ipRange.Vlan, &ipRange.Site, &startIp, &endIp)
		if err != nil {
			logging.Errorf(ctx, "%s", err)
			return []IPRangeRow{}
		}
		ipRange.StartIp = HexStringToIP(startIp).String()
		ipRange.EndIp = HexStringToIP(endIp).String()
		ipRanges = append(ipRanges, ipRange)
	}
	err = rows.Err()
	if err != nil {
		logging.Errorf(ctx, "%s", err)
		return []IPRangeRow{}
	}
	return ipRanges
}

func GetDBHandle() (*sql.DB, error) {
	// TODO(pgervais): do not hard-code the name of the database.
	return sql.Open("mysql", "root@cloudsql(crimson-staging:crimson-staging)/crimson")
}
