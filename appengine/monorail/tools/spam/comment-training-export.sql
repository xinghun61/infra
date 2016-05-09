select IF(c.is_spam, "spam", "ham"), '', REPLACE(c.content, '\n', '\r'), u.email
from SpamVerdict v
join Comment c on c.id = v.comment_id
join User u on u.user_id = c.commenter_id
where
reason="manual" and overruled=0
