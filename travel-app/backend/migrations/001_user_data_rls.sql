-- Run after SQLAlchemy has created the application tables on PostgreSQL.
-- The API sets this transaction-local value from the verified bearer token.

ALTER TABLE user_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_profiles FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS user_profiles_owner ON user_profiles;
CREATE POLICY user_profiles_owner ON user_profiles
    USING (user_id = current_setting('voyara.user_id', true))
    WITH CHECK (user_id = current_setting('voyara.user_id', true));

ALTER TABLE bookings ENABLE ROW LEVEL SECURITY;
ALTER TABLE bookings FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS bookings_owner ON bookings;
CREATE POLICY bookings_owner ON bookings
    USING (user_id = current_setting('voyara.user_id', true))
    WITH CHECK (user_id = current_setting('voyara.user_id', true));

ALTER TABLE itineraries ENABLE ROW LEVEL SECURITY;
ALTER TABLE itineraries FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS itineraries_owner ON itineraries;
CREATE POLICY itineraries_owner ON itineraries
    USING (user_id = current_setting('voyara.user_id', true))
    WITH CHECK (user_id = current_setting('voyara.user_id', true));

ALTER TABLE ai_conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE ai_conversations FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS ai_conversations_owner ON ai_conversations;
CREATE POLICY ai_conversations_owner ON ai_conversations
    USING (user_id = current_setting('voyara.user_id', true))
    WITH CHECK (user_id = current_setting('voyara.user_id', true));

ALTER TABLE ai_memory ENABLE ROW LEVEL SECURITY;
ALTER TABLE ai_memory FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS ai_memory_owner ON ai_memory;
CREATE POLICY ai_memory_owner ON ai_memory
    USING (user_id = current_setting('voyara.user_id', true))
    WITH CHECK (user_id = current_setting('voyara.user_id', true));

ALTER TABLE booking_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE booking_items FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS booking_items_owner ON booking_items;
CREATE POLICY booking_items_owner ON booking_items
    USING (EXISTS (
        SELECT 1 FROM bookings
        WHERE bookings.id = booking_items.booking_id
          AND bookings.user_id = current_setting('voyara.user_id', true)
    ))
    WITH CHECK (EXISTS (
        SELECT 1 FROM bookings
        WHERE bookings.id = booking_items.booking_id
          AND bookings.user_id = current_setting('voyara.user_id', true)
    ));

ALTER TABLE ai_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE ai_messages FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS ai_messages_owner ON ai_messages;
CREATE POLICY ai_messages_owner ON ai_messages
    USING (EXISTS (
        SELECT 1 FROM ai_conversations
        WHERE ai_conversations.id = ai_messages.conversation_id
          AND ai_conversations.user_id = current_setting('voyara.user_id', true)
    ))
    WITH CHECK (EXISTS (
        SELECT 1 FROM ai_conversations
        WHERE ai_conversations.id = ai_messages.conversation_id
          AND ai_conversations.user_id = current_setting('voyara.user_id', true)
    ));
