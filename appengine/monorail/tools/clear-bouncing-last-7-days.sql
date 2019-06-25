-- Cleaer all bouncing email flags for bounces in the last seven days.
-- Accounts that have invalid email addresses will be detected again
-- as soon as one email is sent to that address.

UPDATE User
SET email_bounce_timestamp = NULL
WHERE email_bounce_timestamp > UNIX_TIMESTAMP() - 7 * 24 * 60 * 60
LIMIT 1000;

-- Look at the result, you may want to run it again if 1000 rows were
-- updated because that means that there were more than that many such
-- rows to start.
