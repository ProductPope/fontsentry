# Start here

FontSentry scans your websites, finds the fonts they use, and flags the ones
worth reviewing for **font licensing**. It runs entirely on your own
computer — nothing is uploaded.

**You don't need to be technical.** If you have [Claude Code](https://claude.com/claude-code),
you set everything up by pasting one prompt.

## Set it up with Claude Code

Open Claude Code in this folder and paste this in:

> Set up and run FontSentry for me. I'm not technical, so please install
> anything it needs, build it, and start the local app, then open it in my
> browser at http://127.0.0.1:8000. Once it's running, tell me in plain
> language how to add my websites and run my first check. Keep everything on
> my computer.

Claude Code takes it from there: it installs what's missing, builds the app,
starts it on your machine, and opens it in your browser.

## Then use the app — no code, no files

Everything happens in the browser. The first screen walks you through it:

1. **Add your websites** — the domains you want to check.
2. **Run an audit** — click **Start audit** (top-right). Not ready with your
   real sites? Choose **demo** to see how it works on sample data.
3. **Read the results** — each font gets a plain-language **license verdict**
   (OK / Need check / Violation) and a **privacy verdict** (self-hosted vs
   third-party). Open a row to see *why* and *what to do*.

To record fonts you already have a license for, go to **Registry** and add
them — matching findings then clear automatically on the next audit.

## Privacy

Everything stays on your machine. The app is reachable only from your own
computer (127.0.0.1), and your real website list and licenses are saved to
local files that are never shared or uploaded.

> **Note:** the verdicts are a deterministic aid, **not legal advice**. A
> Violation or Need check means "worth a human checking the license", not
> "infringement".
