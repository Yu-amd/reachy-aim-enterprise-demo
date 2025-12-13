.PHONY: venv install sim run loadgen-local

# Create virtual environment
venv:
	python -m venv .venv

# Install dependencies (requires venv to exist)
install: venv
	. .venv/bin/activate && pip install -U pip && pip install -e .

# Run Reachy Mini daemon in simulation mode
sim:
	. .venv/bin/activate && pip install "reachy-mini[mujoco]" && reachy-mini-daemon --sim --headless

# Run the interactive edge demo
run:
	. .venv/bin/activate && python -m reachy_demo.main

# Run local load generator
loadgen-local:
	. .venv/bin/activate && python -m reachy_demo.tools.loadgen_local
