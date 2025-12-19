"""Structured JSON logging for the demo suite."""

import logging
import sys
import json

class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging."""
    def format(self, record):
        log_record = {
            "level": record.levelname,
            "time": self.formatTime(record, self.datefmt),
            "message": record.getMessage(),
            "name": record.name
        }
        if isinstance(record.msg, dict):
            log_record.update(record.msg)
            log_record.pop("message", None)
        return json.dumps(log_record)

def get_logger(name="demo"):
    """Get a logger with JSON formatting for structured logging."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    logger.propagate = False
    return logger

