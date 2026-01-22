# Calendar Domain

## Sending Calendar Invites

**Always use the `calendar.send_invite` task** - never send raw emails for calendar events.

```python
# Spawn the invite task
from substrate.core.config import DATABASE_URL
from absurd_sdk import Absurd

absurd = Absurd(DATABASE_URL, queue_name='default')
absurd.spawn('calendar.send_invite', {'event_id': 'uuid-here'}, queue='default')
```

This task:
- Generates proper .ics attachment
- Sends to all attendees where `invite_sent = FALSE`
- Marks invites as sent

## Resending/Updating Invites

To resend invites (e.g., after date change):

1. **Reset the invite flags:**
```sql
UPDATE calendar.attendees
SET invite_sent = FALSE, invite_sent_at = NULL
WHERE event_id = 'uuid-here'
```

2. **Spawn the invite task** (same as above)

Do NOT use `email_send` directly - it won't include the .ics calendar attachment.

## Event Flow

```
create_event() → add attendees → spawn calendar.send_invite
                                        ↓
                              generates .ics + sends email
                                        ↓
                              marks invite_sent = TRUE
```

## Attendee Responses

Inbound email replies ("Accepted: Meeting Title") are processed by:
1. Event router matches subject pattern
2. Spawns `calendar.process_response` task
3. Task updates `calendar.attendees.status`

## Related Tasks

| Task | Purpose |
|------|---------|
| `calendar.send_invite` | Send .ics invites to attendees |
| `calendar.send_reminders` | Send reminder emails for upcoming events |
| `calendar.process_response` | Update attendee status from email replies |
| `calendar.create_interaction` | Log CRM interaction after meeting |
