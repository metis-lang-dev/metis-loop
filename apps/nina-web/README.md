# nina-web — the harness UI

The thin browser side of the metis-agent harness (`metis-agent/docs/HARNESS.md`
§5–§6): the browser captures the mic and plays the speech, everything that
understands audio (VAD, whisper, the intent model, RHVoice) stays in Go.

Static files, no bundler. Served by the harness itself:

```bash
cd metis-agent/go && ./bin/fsttm-go -config config.ws.yaml -ui-dir ../../metis-loop/apps/nina-web
# → http://localhost:8392   (localhost counts as a secure context for the mic;
#    off localhost run the harness with ws.tls_* — the fleet CA)
```

| file | role |
|---|---|
| `index.html` | header (link, dialog-state strip, attention switch, audio + mic buttons), chat card + input, events pane, wire log |
| `app.js` | `/ws` connect/reconnect; events → chat (`transcript` = you, `reply` = what was spoken; `intent` dimmed — never `intent.voice`); `command` rows with done / failed / refused / expired buttons that send `task{id,result,detail}`; the WebAudio player (`tts` header + binary s16le chunks, gapless, `tts_done{played_ms}` when playback ends, `tts_stop` flush); the mic (`grab_master` → `role{mic_tok}` → getUserMedia → AudioWorklet → `/ws_mic?tok=`) |
| `mic-worklet.js` | AudioWorkletProcessor: windowed-sinc low-pass, resample to 16 kHz, s16le 20 ms frames (640 bytes) |
| `styles.css` | built Tailwind (committed); rebuild with `npm run build` after changing classes |

Chrome needs one click before it plays audio ("enable audio"; the first
click anywhere also unlocks it). The mic button grabs the mic token: the
engine wakes on a grab and sleeps on a release; the attention switch sends
`attention{AWAKE|ASLEEP}` explicitly.
