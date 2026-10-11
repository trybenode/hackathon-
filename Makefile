.PHONY: dev dev-voice

dev:
	python3 scripts/dev.py

dev-voice:
	python3 scripts/dev.py --voice-worker
