-- Seed: Calendar response routing rules
-- These rules spawn tasks to process calendar responses (accept/decline/tentative)
-- and automatically update attendee status on calendar events.

-- First, ensure name is unique (idempotent)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'rules_name_unique'
    ) THEN
        ALTER TABLE events.rules ADD CONSTRAINT rules_name_unique UNIQUE (name);
    END IF;
END $$;

-- Insert calendar response rules
INSERT INTO events.rules (name, description, enabled, priority, conditions, action, action_config)
VALUES
    (
        'Calendar Accepted',
        'Process emails where attendee accepted a meeting invite',
        true,
        20,
        '{"subject_contains": "Accepted:"}'::jsonb,
        'spawn_task',
        '{"task_name": "calendar.process_response"}'::jsonb
    ),
    (
        'Calendar Declined',
        'Process emails where attendee declined a meeting invite',
        true,
        20,
        '{"subject_contains": "Declined:"}'::jsonb,
        'spawn_task',
        '{"task_name": "calendar.process_response"}'::jsonb
    ),
    (
        'Calendar Tentative',
        'Process emails where attendee tentatively accepted a meeting invite',
        true,
        20,
        '{"subject_contains": "Tentative:"}'::jsonb,
        'spawn_task',
        '{"task_name": "calendar.process_response"}'::jsonb
    )
ON CONFLICT (name) DO UPDATE SET
    description = EXCLUDED.description,
    conditions = EXCLUDED.conditions,
    action = EXCLUDED.action,
    action_config = EXCLUDED.action_config,
    updated_at = now();
