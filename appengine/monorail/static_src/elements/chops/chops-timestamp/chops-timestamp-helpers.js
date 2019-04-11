// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

const DEFAULT_DATE_LOCALE = 'en-US';

// Creating the datetime formatter costs ~1.5 ms, so when formatting
// multiple timestamps, it's more performant to reuse the formatter object.
// Export FORMATTER and SHORT_FORMATTER for testing. The return value differs
// based on time zone and browser, so we can't use static strings for testing.
// We can't stub out the method because it's native code and can't be modified.
// https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/DateTimeFormat/format#Avoid_comparing_formatted_date_values_to_static_values
export const FORMATTER = new Intl.DateTimeFormat(DEFAULT_DATE_LOCALE, {
  weekday: 'short',
  year: 'numeric',
  month: 'short',
  day: 'numeric',
  hour: 'numeric',
  minute: '2-digit',
  timeZoneName: 'short',
});

export const SHORT_FORMATTER = new Intl.DateTimeFormat(DEFAULT_DATE_LOCALE, {
  year: 'numeric',
  month: 'short',
  day: 'numeric',
});

export function standardTime(date) {
  if (!date) return;
  const absoluteTime = FORMATTER.format(date);
  const timeAgo = relativeTime(date);
  const timeAgoBit = timeAgo ? ` (${timeAgo})` : '';
  return `${absoluteTime}${timeAgoBit}`;
}

export function standardTimeShort(date) {
  if (!date) return;
  // For a "short" timestamp, display relative time or a short absolute time
  // if it's been a long time.
  const timeAgo = relativeTime(date);
  if (timeAgo) return timeAgo;
  return SHORT_FORMATTER.format(date);
}

export function relativeTime(date) {
  if (!date) return;

  const now = new Date();
  let secondDiff = Math.floor((now.getTime() - date.getTime()) / 1000);

  // Use different wording depending on whether the time is in the
  // future or past.
  const pastOrPresentSuffix = secondDiff < 0 ? 'from now' : 'ago';

  secondDiff = Math.abs(secondDiff);
  const minuteDiff = Math.floor(secondDiff / 60);
  const hourDiff = Math.floor(minuteDiff / 60);
  const dayDiff = Math.floor(hourDiff / 24);

  if (!minuteDiff) {
    // Less than a minute.
    return 'just now';
  } else if (!hourDiff) {
    // Less than an hour.
    if (minuteDiff === 1) {
      return `a minute ${pastOrPresentSuffix}`;
    }
    return `${minuteDiff} minutes ${pastOrPresentSuffix}`;
  } else if (!dayDiff) {
    // Less than an day.
    if (hourDiff === 1) {
      return `an hour ${pastOrPresentSuffix}`;
    }
    return `${hourDiff} hours ${pastOrPresentSuffix}`;
  } else if (dayDiff < 30) {
    // Less than a month.
    if (dayDiff === 1) {
      return `a day ${pastOrPresentSuffix}`;
    }
    return `${dayDiff} days ${pastOrPresentSuffix}`;
  }

  // Don't show relative time if it's been a long time ago.
  return '';
}
