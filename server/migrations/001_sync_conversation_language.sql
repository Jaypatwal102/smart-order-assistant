BEGIN;

ALTER TABLE conversations
    ADD COLUMN IF NOT EXISTS detected_language VARCHAR(10);

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name = 'user_sessions'
          AND column_name = 'detected_language'
    ) THEN
        UPDATE conversations AS conversation
        SET detected_language = COALESCE(session.detected_language, 'en')
        FROM user_sessions AS session
        WHERE conversation.session_id = session.session_id
          AND conversation.detected_language IS NULL;
    END IF;
END
$$;

UPDATE conversations
SET detected_language = 'en'
WHERE detected_language IS NULL;

ALTER TABLE conversations
    ALTER COLUMN detected_language SET DEFAULT 'en',
    ALTER COLUMN detected_language SET NOT NULL;

ALTER TABLE users
    DROP CONSTRAINT IF EXISTS ck_users_role;
ALTER TABLE users
    DROP COLUMN IF EXISTS role;

ALTER TABLE user_sessions
    DROP CONSTRAINT IF EXISTS ck_user_sessions_device_type;
ALTER TABLE user_sessions
    DROP COLUMN IF EXISTS device_type,
    DROP COLUMN IF EXISTS detected_language;

ALTER TABLE intent_training_phrases
    ALTER COLUMN intent_id SET NOT NULL,
    DROP CONSTRAINT IF EXISTS intent_training_phrases_created_by_fkey;
ALTER TABLE intent_training_phrases
    ADD CONSTRAINT intent_training_phrases_created_by_fkey
    FOREIGN KEY (created_by) REFERENCES users(user_id) ON DELETE SET NULL;

ALTER TABLE messages
    ALTER COLUMN conversation_id SET NOT NULL;

ALTER TABLE bot_routing_logs
    ALTER COLUMN message_id SET NOT NULL;

ALTER TABLE fallback_handoffs
    ALTER COLUMN conversation_id SET NOT NULL,
    DROP CONSTRAINT IF EXISTS fallback_handoffs_trigger_message_id_fkey,
    DROP CONSTRAINT IF EXISTS fallback_handoffs_assigned_agent_id_fkey;
ALTER TABLE fallback_handoffs
    ADD CONSTRAINT fallback_handoffs_trigger_message_id_fkey
    FOREIGN KEY (trigger_message_id) REFERENCES messages(message_id) ON DELETE SET NULL,
    ADD CONSTRAINT fallback_handoffs_assigned_agent_id_fkey
    FOREIGN KEY (assigned_agent_id) REFERENCES users(user_id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS ix_user_sessions_user_id
    ON user_sessions(user_id);
CREATE INDEX IF NOT EXISTS ix_conversations_session_id
    ON conversations(session_id);
CREATE INDEX IF NOT EXISTS ix_messages_conversation_id
    ON messages(conversation_id);
CREATE INDEX IF NOT EXISTS ix_bot_routing_logs_message_id
    ON bot_routing_logs(message_id);
CREATE INDEX IF NOT EXISTS ix_fallback_handoffs_conversation_id
    ON fallback_handoffs(conversation_id);
CREATE INDEX IF NOT EXISTS ix_fallback_handoffs_trigger_message_id
    ON fallback_handoffs(trigger_message_id);
CREATE INDEX IF NOT EXISTS ix_fallback_handoffs_assigned_agent_id
    ON fallback_handoffs(assigned_agent_id);
CREATE INDEX IF NOT EXISTS ix_intent_training_phrases_intent_id
    ON intent_training_phrases(intent_id);
CREATE INDEX IF NOT EXISTS ix_intent_training_phrases_created_by
    ON intent_training_phrases(created_by);
CREATE INDEX IF NOT EXISTS ix_fallback_review_queue_assigned_to_intent
    ON fallback_review_queue(assigned_to_intent);

COMMIT;
