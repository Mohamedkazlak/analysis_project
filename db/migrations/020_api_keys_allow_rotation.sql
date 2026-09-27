-- Remote migration 018 created a partial unique index on api_keys.user_id.
-- A revoked or expired key must be able to remain while a replacement is issued.
-- key_hash stays unique.

drop index if exists api_keys_user_id_key;
