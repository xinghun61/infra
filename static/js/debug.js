// Copyright (c) 2009 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

/**
 * Hacky helpers for debugging...
 */

function Log(msg) {
  var d = document.getElementById('log');
  d.appendChild(document.createTextNode(msg + "\n"));
}

function DumpTimestamp(t) {
  var d = new Date();
  d.setTime(t);
  return d.toLocaleString();
}

function DumpUTCTimestamp(t) {
  var d = new Date();
  d.setTime(t);
  return d.toUTCString();
}

function DumpObj(obj, opt_name) {
  if (typeof obj == "string") {
    return "\"" + obj.toString() + "\"";
  }

  if (typeof obj != "object") {
    return "" + obj
  }

  var str = "";

  if (obj instanceof Array) {
    for (var i = 0; i < obj.length; ++i) {
      if (i > 0)
        str += ", ";
      str += DumpObj(obj[i]);
    }
    return "[" + str + "]";
  }

  var i = 0;
  for (var key in obj) {
    if (typeof obj[key] == "function") {
      continue;
    }
    if (i > 0)
      str += ", ";
    str += key + ": " + DumpObj(obj[key]);
    i++;
  }

  return "{" + str + "}";
}

function LogRun(run) {
  Log("startTime: " + DumpTimestamp(run.startTime));
  Log("endTime: " + DumpTimestamp(run.GetEndTime()));
  Log("duration (minutes): " + run.duration / (1000 * 60));
  Log("timestamp: " + DumpTimestamp(run.entry.timestamp));
}

function LogObject(obj, opt_name) {
  var prefix = "";
  if (opt_name)
   prefix = opt_name + "= ";
  Log(prefix + DumpObj(obj));
}

