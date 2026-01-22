-- Create separate queues for different task types
-- This allows long-running schedulers to not block one-off tasks

-- Obsidian queue for vault sync (long-running)
SELECT absurd.create_queue('obsidian');

-- Email queue for resend sync (long-running)
SELECT absurd.create_queue('email');

-- Default queue already exists for one-off tasks
