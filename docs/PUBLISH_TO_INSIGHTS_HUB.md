# "Publish to Insights Hub" - add this to your recurring chats

This is the step to paste into your existing Claude chats, Cowork tasks,
or a shared Claude Project's instructions, so that **the end of every
successful run automatically publishes its output to the Insights Hub** -
no downloading a file and re-uploading it, no editing
`data/dashboards.json`, no manual "add this week" step.

**Claude Code cannot do this step for you.** This session has no way to
read or edit your claude.ai chats, projects, or Cowork task settings -
those live in a completely separate product surface with no API or tool
this session can reach. You need to paste the block below into each
relevant chat/task yourself. See "Where to paste this" below.

---

## The instruction block (copy everything in the box)

```
## Publish to Insights Hub

At the end of this workflow, once your analysis is complete and correct:

1. Produce the output format(s) this topic normally uses (HTML dashboard,
   PPTX, DOCX, or PDF - whichever you'd normally hand back).

2. Make sure the Google Drive connector is turned on for this chat. Upload
   your output file(s) into this Drive folder:

       <SHARED_DRIVE_FOLDER_URL_GOES_HERE>

   inside a subfolder named exactly after this workflow's id:

       <SHARED_DRIVE_FOLDER_URL_GOES_HERE>/<WORKFLOW_ID_GOES_HERE>/

   (Ask whoever maintains the Insights Hub repo for the exact folder URL
   and workflow id if you don't have them - they're in
   data/research_register.json in the rosebasil/insighthub repo. If this
   is a brand-new recurring topic that isn't in that file yet, pick a
   short lowercase-hyphenated id for it, e.g. "wf-your-topic-name", and
   say so plainly in your final message so it can be added to the
   register.)

3. In the same Drive subfolder, upload one more file: a manifest named
   `<run_id>.meta.json`, where run_id is `<WORKFLOW_ID>-<period_start>`
   (e.g. "wf-driver-nps-2026-09-20"). Its content must be exactly this
   JSON shape (all fields required unless noted optional):

   {
     "run_id": "<WORKFLOW_ID>-<period_start, YYYY-MM-DD>",
     "workflow_id": "<WORKFLOW_ID>",
     "topic": "<human-readable topic name>",
     "source": "SurveyMonkey" | "Snowflake" | "Mixed" | "Manual",
     "owner": "<your email>",
     "cadence": "weekly" | "biweekly" | "on-demand",
     "period_start": "YYYY-MM-DD",
     "period_end": "YYYY-MM-DD",
     "market": "All" | "KSA" | "Jordan",
     "audience": "All" | "Driver" | "Passenger",
     "data_as_of": "<ISO 8601 timestamp - when you pulled the data>",
     "output_formats": ["dashboard_html"] and/or ["pptx"], ["docx"], ["pdf"],
     "files": [
       {"format": "dashboard_html", "path": "<run_id>.html"},
       {"format": "pptx", "path": "<run_id>.pptx"}
     ],
     "version": 1,
     "source_references": ["<table name, survey id, or other source ref>"],
     "status": "published",
     "generated_at": "<ISO 8601 timestamp>",
     "generated_by": "<this chat's name or a link to it, if you have one>"
   }

   `files[].path` must be just the filename (no folder path) - it's
   assumed to sit next to the manifest in the same Drive subfolder. Every
   path listed must be a file you actually uploaded in step 2 - the hub
   validates this and will NOT show a run whose file is missing.

4. Confirm the upload actually succeeded (check the Drive connector's own
   confirmation, not just that you didn't see an error) before you tell
   the person running this chat that publishing worked. If anything
   failed - the Drive connector isn't enabled, an upload errored, you
   couldn't reach the folder - set "status": "failed" in the manifest (or
   skip uploading the manifest entirely) and say plainly in your final
   message that publishing did not complete and why. Never say "published"
   when the files aren't actually sitting in Drive.

The Insights Hub checks that Drive folder on its own schedule (currently
every 3 hours) and picks up new or revised runs automatically - nothing
else to do on your end once the upload succeeds.
```

---

## Where to paste this

- **A shared Claude Project** (e.g. if your weekly/biweekly SurveyMonkey
  chats live under one Project): add the block to the Project's custom
  instructions once - every chat in that Project picks it up.
- **An individual recurring chat** not in a shared Project: paste it at
  the end of that chat's own system/instructions, or as the last message
  in the prompt you re-send each run.
- **A Cowork task**: add it to the task's instructions the same way -
  Cowork tasks accept the same kind of prompt text.

Paste it once per chat/task; you don't need to repeat it every run.

## The one-time setup this needs from you

1. **Create a shared Google Drive folder** (or reuse one) that both (a)
   every relevant Claude chat can reach via its own Drive connector, and
   (b) a Google Cloud service account can also read. These are two
   separate credentials - a chat's Drive connector is your own OAuth
   session; the hub's own read access is a service account with no
   connection to your chat sessions at all. See README.md "Connecting
   real data sources" → Google Drive for the exact service-account setup
   and how to share the folder with it.
2. **Give each chat/task the folder URL and its workflow_id** by filling
   in the two placeholders in the block above before you paste it.
3. **Turn the Drive connector on** in each chat/task (Settings → Connectors
   in claude.ai, or the task's own connector toggle in Cowork).
4. **Tell whoever maintains this repo** the workflow_id, topic, owner,
   source, cadence, market, and audience for any topic not already in
   `data/research_register.json`, so it shows up in the Studies Library
   even before its first run lands.

## What this does NOT do

- It does not let the Insights Hub read your chat history, your
  conversation, or anything you didn't explicitly upload to the shared
  Drive folder as a finished file.
- It does not run automatically inside a chat - a chat only publishes
  when it (or its owner) actually runs it and reaches this step.
- It does not replace the two workflows that already publish without any
  chat at all: `scripts/run_no_rides_after_signup.py` and
  `scripts/run_in_app_reviews_report.py` run entirely inside GitHub
  Actions on a schedule, straight from Snowflake, with no Claude chat or
  Drive step in the loop. Use this Drive-based instruction only for
  workflows that genuinely need a Claude chat's judgment (SurveyMonkey
  analysis, anything Snowflake alone can't answer).
