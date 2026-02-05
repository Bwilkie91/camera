# Unified Activity View — UX and Research

The **Activity** page is a single data-rich container that replaces four separate pages (Events, Behaviors, Timeline, Log) to reduce redundancy and cognitive load while keeping all analysis in one place.

## Research principles applied

- **Single container, multiple views**: Tabbed dashboards (e.g. Splunk, monitoring UIs) keep one interface and switch context via tabs instead of separate pages. Users get consistency and less navigation.
- **Intentional information density**: Dense data is acceptable when structure is clear: one panel, clear tab labels (Feed, Events, Log, Charts), and predictable layout.
- **Activity feed ordering**: Time-ordered feeds (newest first) match how operators scan for recent events; the **Feed** tab merges events and AI data by timestamp so both streams appear in one timeline.
- **Decision assistant, not passive display**: Events tab keeps filters and **Acknowledge** so high-priority and “Needs review” items are actionable without leaving the container.
- **Avoiding tool sprawl**: One place for “what happened” (feed, events, log, charts) reduces switching between Events, Timeline, Log, and Behaviors and keeps one URL to bookmark or share.

## Structure

| Tab    | Content | Replaces |
|--------|---------|----------|
| **Feed**   | Merged time-ordered list: events (with Ack) and AI detection rows; “Event” vs “Detection” badge. | Timeline + Log combined view. |
| **Events** | Events only: type/severity/ack filters, search, acknowledge. | Events page. |
| **Log**    | AI data only: date, time, event, object, emotion, pose, scene, crowd. | Activity log (Log) page. |
| **Charts** | Activity by hour (bar chart), summary by event type (motion, loitering, line_cross, total). | Behaviors page summary + chart. |

- **Range** (Last 24h, Last 7 days, All) applies to Feed, Events, and Log; Charts use the same range for aggregates.
- Old URLs still work: `/events`, `/timeline`, `/log`, `/behaviors` redirect to Activity with the correct tab selected.

## Navigation and Dashboard

- **Nav**: One link **Activity** replaces Events, Behaviors, Timeline, and Log. Dashboard, Live, Map, Analytics, Export, Settings unchanged.
- **Dashboard**: Cards (Recording, Events today, Unacknowledged, Streams) and “Today” summary now link to `/activity` or `/activity?view=events`; “View all in Activity” replaces duplicate event breakdown text.
- **New event toast**: “View Activity” links to `/activity?view=events`.

## What stayed separate

- **Analytics**: Full date-range aggregates table (by date/hour/event/camera) remains its own page for power users and export-oriented workflows.
- **Map**: Camera positions and site map; different mental model (spatial).
- **Live**: Streams and recording control; real-time video, not historical data.
- **Export / Settings**: Unchanged.

## References

- Building a Unified Monitoring Dashboard to Combat Tool Sprawl (Algomox).
- Lessons from Redesigning a Multi-Product Developer Dashboard (GetStream); intentional density and consistency.
- The Ultimate Guide to Designing Activity Feeds (GetStream); ordering and personalization.
- UX Strategies For Real-Time Dashboards (Smashing Magazine); dashboards as decision assistants.
- Tabbed Dashboards (Splunk); organizing multiple views in one container.
