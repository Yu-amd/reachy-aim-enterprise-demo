.PHONY: venv install install-system-deps stop-daemon stop sim sim-gui run loadgen-local

# Create virtual environment
venv:
	python3 -m venv .venv

# Install system dependencies (PortAudio for sounddevice)
install-system-deps:
	@echo "Checking for PortAudio library..."
	@if ! pkg-config --exists portaudio-2.0 2>/dev/null && ! ldconfig -p | grep -q libportaudio 2>/dev/null; then \
		echo "PortAudio not found. Attempting to install..."; \
		if command -v apt-get >/dev/null 2>&1; then \
			sudo apt-get update && sudo apt-get install -y libportaudio2 portaudio19-dev || echo "Warning: Failed to install PortAudio. Please install manually: sudo apt-get install libportaudio2 portaudio19-dev"; \
		elif command -v dnf >/dev/null 2>&1; then \
			sudo dnf install -y portaudio-devel || echo "Warning: Failed to install PortAudio. Please install manually: sudo dnf install portaudio-devel"; \
		elif command -v yum >/dev/null 2>&1; then \
			sudo yum install -y portaudio-devel || echo "Warning: Failed to install PortAudio. Please install manually: sudo yum install portaudio-devel"; \
		elif command -v pacman >/dev/null 2>&1; then \
			sudo pacman -S --noconfirm portaudio || echo "Warning: Failed to install PortAudio. Please install manually: sudo pacman -S portaudio"; \
		else \
			echo "Warning: Could not detect package manager. Please install PortAudio manually for your distribution."; \
		fi \
	else \
		echo "PortAudio library found."; \
	fi

# Install dependencies (requires venv to exist)
install: venv install-system-deps
	. .venv/bin/activate && pip install -U pip && pip install -e .

# Stop any running reachy-mini-daemon processes
stop-daemon:
	@echo "Checking for running reachy-mini-daemon processes..."
	@bash -c 'set +e; \
	PIDS=$$(pgrep -f "reachy-mini-daemon" 2>/dev/null | grep -v $$$$ || true); \
	if [ -n "$$PIDS" ]; then \
		echo "Stopping reachy-mini-daemon processes (PIDs: $$PIDS)..."; \
		echo $$PIDS | xargs -r kill 2>/dev/null || true; \
		sleep 1; \
		REMAINING=$$(pgrep -f "reachy-mini-daemon" 2>/dev/null | grep -v $$$$ || true); \
		if [ -n "$$REMAINING" ]; then \
			echo "Force killing remaining processes..."; \
			echo $$REMAINING | xargs -r kill -9 2>/dev/null || true; \
			sleep 0.5; \
		fi; \
	fi; \
	FINAL_CHECK=$$(ps aux | grep -E "[r]eachy-mini-daemon" | wc -l); \
	if [ "$$FINAL_CHECK" -gt 0 ]; then \
		echo "Warning: Some processes may still be running."; \
	else \
		echo "All reachy-mini-daemon processes stopped."; \
	fi'

# Stop any running application instances
stop:
	@echo "Checking for running application processes..."
	@bash -c 'set +e; \
	PIDS=$$(pgrep -f "reachy_demo.main" 2>/dev/null | grep -v $$$$ || true); \
	if [ -n "$$PIDS" ]; then \
		echo "Stopping application processes (PIDs: $$PIDS)..."; \
		echo $$PIDS | xargs -r kill 2>/dev/null || true; \
		sleep 1; \
		REMAINING=$$(pgrep -f "reachy_demo.main" 2>/dev/null | grep -v $$$$ || true); \
		if [ -n "$$REMAINING" ]; then \
			echo "Force killing remaining processes..."; \
			echo $$REMAINING | xargs -r kill -9 2>/dev/null || true; \
			sleep 0.5; \
		fi; \
	fi; \
	FINAL_CHECK=$$(ps aux | grep -E "[r]eachy_demo.main" | wc -l); \
	if [ "$$FINAL_CHECK" -gt 0 ]; then \
		echo "Warning: Some processes may still be running."; \
	else \
		echo "All application processes stopped."; \
	fi'

# Run Reachy Mini daemon in simulation mode (port 8001 to avoid AIM port conflicts)
sim: stop-daemon
	. .venv/bin/activate && pip install "reachy-mini[mujoco]" && reachy-mini-daemon --sim --headless --fastapi-port 8001

# Run Reachy Mini daemon with GUI (MuJoCo viewer visible)
sim-gui: stop-daemon
	. .venv/bin/activate && pip install "reachy-mini[mujoco]" && reachy-mini-daemon --sim --fastapi-port 8001

# Run the interactive edge demo
run: stop
	. .venv/bin/activate && python3 -m reachy_demo.main

# Run local load generator
loadgen-local:
	. .venv/bin/activate && python3 -m reachy_demo.tools.loadgen_local
