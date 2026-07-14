import logging
import sys
from pathlib import Path

LOG_FORMAT = "%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s"

def setup_logger():
    """Configures the global logging setup for the application."""
    
    # 🎯 FIX: Pathlib automatically corrects all Windows/Linux slash issues!
    # This grabs the absolute folder where logger.py lives, moves up 3 levels to 'backend', and creates app.log there.
    backend_dir = Path(__file__).resolve().parent.parent.parent
    log_file_path = backend_dir / "app.log"
    
    print(f"\n🪵 LOGGER INITIALIZED! Explicitly writing to: {log_file_path}\n")
    
    logging.basicConfig(
        level=logging.INFO,
        format=LOG_FORMAT,
        handlers=[
            logging.FileHandler(str(log_file_path), encoding="utf-8"),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    return logging.getLogger("researchmind_ai")

logger = setup_logger()