# Desktop update: run and verify

The files have already been updated in E:\SecureRAG. No replacement copy/paste is needed.

## 1. Close the previous app
Finish any current request and close its window. The running Python process cannot pick up these edits automatically.

## 2. Run regression tests
From PowerShell:

```powershell
cd E:\SecureRAG
.\.venv\Scripts\Activate.ps1
python -m pytest tests/test_document_routing.py tests/test_desktop.py -q
```

The desktop test uses a fake backend and runs offscreen. The routing tests check the security boundaries with controlled classifier results, not model accuracy. tests/ui_preview.png is an offscreen preview from a fake conversation.

## 3. Start the app

```powershell
python main.py gui
```

Wait until the bottom status says Ready. Open Settings at the bottom of the sidebar, click Refresh models, select an installed model, then Connect. Click Done to return to chat. If Ollama is unavailable, start the Ollama desktop app first.

## 4. Test the document fix
Upload a benign document, or select DES.pdf if it is already indexed. An approved upload selects the document and switches to Ask documents automatically. The text below the heading shows the active source.

Click Summarize selected document, or ask "What is this document about?". The app reads that document's indexed excerpts directly, then verifies their hashes and screens them again. It does not reject a general overview request for lacking topic keywords.

Ask a specific follow-up such as "What key size does DES use?". This uses semantic search restricted to the selected file. The relevance cutoff still applies to these specific questions. The chat is currently single-turn: earlier messages are displayed but are not sent as conversational memory.

For long files, an overview currently uses up to the first eight indexed excerpts and explicitly states the coverage. It must not be presented as a full long-document summary. A whole-document summarization pipeline is future work.

## 5. Test quarantine visibility
Upload your poisoned test document. A fully blocked file should show an amber banner stating that nothing from the file can be retrieved. The library still lists the file as Blocked so you can see the decision. It is not available as context.

A file with both approved and blocked chunks shows Partially approved. Only approved chunks are indexed. Select it and summarize: quarantined content stays excluded.

If two rows have the same filename, hover over them to compare their complete paths. File identity is currently its full path, not its display name.

## 6. Interaction checks
- Enter sends; Shift+Enter inserts a newline.
- Copy copies a finished, checked answer.
- New conversation clears the visible transcript only.
- Settings > Reduce motion disables message fades, animated scrolling and sidebar transitions.
- The top-left sidebar icon expands or collapses the document library with a short eased transition.
- Model selection is in Settings; the main conversation uses a neutral white and gray design with a centered reading column.
- One file can be dropped at a time. Controls stay disabled during an operation.
- Security activity reflects the latest completed operation.
- Removing a document deletes its index entries, not the original file.
- Closing during an operation asks you to wait. Generation has a network timeout but no cancellation button yet.

## Files changed
- src/gui/app.py: redesigned native Qt interface, animated message appearance and scrolling, scope label, explicit upload decisions, keyboard controls, safer busy state, fresh audit view.
- src/storage/store.py: source-scoped semantic retrieval and ordered indexed excerpts for summaries.
- src/rag/pipeline.py: selected source and overview routing, per-excerpt rechecks, partial approval status and honest overview coverage.
- tests/test_document_routing.py: routing and guard regression tests.
- tests/test_desktop.py: offscreen interaction/render test with a fake backend.

The frozen classifier and evaluation datasets were not modified. Tests passing do not guarantee perfect detection or generation. Run the app with your actual DES.pdf and Ollama model before packaging. Existing installed EXEs must be rebuilt to include these changes; the launch command above runs the updated source.
