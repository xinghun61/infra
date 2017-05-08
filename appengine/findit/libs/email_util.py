# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

def ObscureEmails(emails, domains):
  """Obscures the given emails that are in the given domains."""
  obscured_emails = []
  for email in emails:
    parts = email.split('@', 2)
    if len(parts) < 2 or parts[1] in domains:
      # For any whitelisted App Engine service account, keep it as is.
      parts[0] = 'x' * len(parts[0])
    obscured_emails.append('@'.join(parts))
  return obscured_emails
