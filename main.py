"""Entrypoint for hosting/platforms that expect a `main.py` or `app.py`.
This simply starts the scheduler.
"""

from src import scheduler_main

if __name__ == '__main__':
    scheduler_main.main()
