"""
Latency Policy for Enterprise-Responsive Robot Gestures

This module implements a latency-aware gesture selection policy that provides
immediate feedback and appropriate gestures based on response latency.

Latency Budget (Target E2E: 2500ms):
- Input capture + prompt build: 50ms
- Robot state fetch (optional): 50-150ms
- Network hop to inference endpoint:
  - Local LMStudio: <10ms
  - Remote AIM: 20-100+ms
- Model response latency (dominant): 400-2000+ms
- Post-processing + action decision: 20-50ms
- Robot gesture command: 50-250ms

Gesture Tiers (Enterprise-Responsive):
- Tier 0 (fast): <800ms → ack + quick nod (nod_fast)
- Tier 1 (normal): 800-2500ms → ack + engaged tilt (nod_tilt)
- Tier 2 (slow): >2500ms → ack + "thinking hold" then done (thinking_done)
- Error: inference failures → shake/no or sad posture (error)
"""

from __future__ import annotations
import logging

logger = logging.getLogger(__name__)


class LatencyPolicy:
    """
    Latency-aware gesture selection policy.
    
    Provides immediate feedback and selects appropriate gestures based on
    measured latency to create an enterprise-responsive user experience.
    """
    
    # Latency tier thresholds (milliseconds)
    TIER_0_THRESHOLD = 800   # Fast response
    TIER_1_THRESHOLD = 2500  # Normal response (SLO target)
    # Tier 2 is anything above TIER_1_THRESHOLD (slow response)
    
    def __init__(self):
        """Initialize the latency policy."""
        pass
    
    def choose_pre_gesture(self) -> str:
        """
        Choose gesture to show immediately when user input is received.
        
        This provides instant feedback that the system is processing the request.
        
        Returns:
            Gesture name for immediate feedback (always "ack" for acknowledgment)
        """
        return "ack"
    
    def choose_post_gesture(
        self,
        aim_ms: float,
        e2e_ms: float,
        ok: bool,
    ) -> str:
        """
        Choose gesture based on measured latency and success status.
        
        Args:
            aim_ms: AIM/LLM call latency in milliseconds
            e2e_ms: End-to-end latency in milliseconds (from user input to response)
            ok: Whether the request succeeded (True) or failed (False)
        
        Returns:
            Gesture name appropriate for the latency tier and status
        """
        if not ok:
            # Error case: show error gesture
            logger.info(f"⚠ Error detected - selecting error gesture (e2e={e2e_ms:.0f}ms)")
            return "error"
        
        # Success case: select based on latency tier
        if e2e_ms < self.TIER_0_THRESHOLD:
            # Tier 0: Fast response (<800ms)
            logger.info(f"✓ Tier 0 (fast): e2e={e2e_ms:.0f}ms, aim={aim_ms:.0f}ms → nod_fast")
            return "nod_fast"
        elif e2e_ms < self.TIER_1_THRESHOLD:
            # Tier 1: Normal response (800-2500ms)
            logger.info(f"✓ Tier 1 (normal): e2e={e2e_ms:.0f}ms, aim={aim_ms:.0f}ms → nod_tilt")
            return "nod_tilt"
        else:
            # Tier 2: Slow response (>2500ms, SLO miss)
            logger.info(f"⚠ Tier 2 (slow): e2e={e2e_ms:.0f}ms, aim={aim_ms:.0f}ms → thinking_done")
            return "thinking_done"
    
    def get_latency_tier(self, e2e_ms: float) -> int:
        """
        Get the latency tier for a given end-to-end latency.
        
        Args:
            e2e_ms: End-to-end latency in milliseconds
        
        Returns:
            Tier number (0=fast, 1=normal, 2=slow)
        """
        if e2e_ms < self.TIER_0_THRESHOLD:
            return 0
        elif e2e_ms < self.TIER_1_THRESHOLD:
            return 1
        else:
            return 2

