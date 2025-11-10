"""
Simple entrypoint wrapper for Render: execute the original script file (which has
a space in its name) using runpy so Render can use a clean start command `python bot.py`.
"""
import runpy
import sys

if __name__ == "__main__":
    # Execute the original script in its own __main__ namespace
    runpy.run_path("python philosophy_bot.py", run_name="__main__")
