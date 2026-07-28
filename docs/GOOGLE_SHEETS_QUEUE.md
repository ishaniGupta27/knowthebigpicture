# Google Sheets video queue

The scheduled workflow reads one approved idea from Google Sheets every two
hours, produces its video, copies the job to Google Drive, uploads a YouTube
Short, and updates the row.

## Sheet

The spreadsheet file may have any name and may live anywhere in Google Drive.
Its worksheet tab must be named exactly `VideoQueue`.

Row 1 must contain these exact headers in this order:

```text
id	status	format	topic	number_of_items	youtube_public	publish_instagram	created_at	started_at	completed_at	output_url	error	retry_count
```

Example rows:

```text
id	status	format	topic	number_of_items	youtube_public	publish_instagram	created_at	started_at	completed_at	output_url	error	retry_count
1	new	why	Why does pineapple burn your tongue?		FALSE	FALSE	2026-07-27					0
2	new	types	10 Types of Dumplings Explained	10	FALSE	FALSE	2026-07-27					0
3	new	myth_vs_fact	Is brown rice always healthier than white rice?		TRUE	FALSE	2026-07-27					0
```

The worker recognizes these states:

- `new`: saved idea; ignored by automation.
- `pending`: approved and waiting for production.
- `processing`: claimed by the current workflow run.
- `done`: generated, copied to Drive, and uploaded.
- `failed`: production or upload failed.

The normal flow is `new → pending → processing → done`. To retry a failed row,
change its status from `failed` to `pending`. Blank statuses are ignored.

IDs must be numeric and unique. Supported formats are `why`, `how`, `types`,
`comparison`, `what_is_it`, and `myth_vs_fact`. `number_of_items` is optional
and only applies to `types`; when blank, the leading number in the topic is
used, or 5 if no number is present.

Every completed video is uploaded to YouTube as a Short:

- `youtube_public=TRUE` uploads it publicly.
- `youtube_public=FALSE` or blank uploads it privately.

Instagram is opt-in. It is attempted only when `publish_instagram=TRUE`.

## Google authentication

Enable the Google Sheets API in the Google Cloud project, create a service
account and JSON key, and share only the queue spreadsheet with the service
account's `client_email` as an Editor. The spreadsheet does not need to be
public or moved to a special folder.

Add these GitHub Actions repository secrets:

- `GOOGLE_SERVICE_ACCOUNT_JSON`: complete contents of the service-account JSON.
- `GOOGLE_SHEET_ID`: text between `/d/` and `/edit` in the Sheet URL.
- `RCLONE_CONFIG`: rclone config containing the `kbpdrive` remote.
- `OPENAI_API_KEY`
- `YOUTUBE_CLIENT_ID`
- `YOUTUBE_CLIENT_SECRET`
- `YOUTUBE_REFRESH_TOKEN`
- `INSTAGRAM_ACCESS_TOKEN` and `INSTAGRAM_USER_ID` when Instagram is used.

The Sheets service account is independent from YouTube OAuth and rclone.

## Operation

The `Produce Next Queued Video` workflow:

1. Runs at minute 17 every two hours, or manually through `workflow_dispatch`.
2. Selects the pending row with the lowest numeric ID.
3. Immediately marks it `processing`.
4. Performs a real, full video generation.
5. Uploads a public or private YouTube Short.
6. Optionally publishes to Instagram.
7. Copies the job to `kbpdrive:jobs/<id>`.
8. Marks the row `done` and stores the YouTube Shorts URL.

Only one queue workflow can run at a time. If a step fails after a row is
claimed, the row is marked `failed`, the attempt count is incremented, and the
GitHub Actions run URL is written to `error`.

Test the connection by leaving all rows as `new`, manually running **Produce
Next Queued Video**, and confirming it reports an empty queue. Then change one
row to `pending` and run it manually before relying on the schedule.
