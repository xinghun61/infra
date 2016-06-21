-- Copyright 2016 The Chromium Authors. All Rights Reserved.
--
-- Use of this source code is governed by a BSD-style
-- license that can be found in the LICENSE file or at
-- https://developers.google.com/open-source/licenses/bsd

-- Create tables in the crimson DB.

CREATE TABLE ip_range (
  site varchar(20) NOT NULL,
  vlan varchar(20),
  start_ip varbinary(16) NOT NULL,
  end_ip varbinary(16) NOT NULL
) ENGINE=INNODB;
