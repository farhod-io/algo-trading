import asyncio
import logging
from typing import Callable, Any, Dict, List

class EventBus:
    """
    A simple centralized Event Bus for handling decoupled communication 
    between different modules (e.g. Signal Generator -> Notifier).
    """
    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = {}

    def subscribe(self, event_type: str, callback: Callable):
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(callback)
        logging.debug(f"Subscribed to {event_type}")

    def publish(self, event_type: str, *args, **kwargs):
        if event_type not in self._subscribers:
            return
            
        for callback in self._subscribers[event_type]:
            try:
                # If the callback is a coroutine, we should handle it,
                # but currently we assume synchronous or we run it properly.
                if asyncio.iscoroutinefunction(callback):
                    # We create a task if we are in a running loop, 
                    # otherwise we might need asyncio.run if called from thread
                    try:
                        loop = asyncio.get_running_loop()
                        loop.create_task(callback(*args, **kwargs))
                    except RuntimeError:
                        asyncio.run(callback(*args, **kwargs))
                else:
                    callback(*args, **kwargs)
            except Exception as e:
                logging.error(f"Error in event subscriber for {event_type}: {e}")

# Global singleton event bus
event_bus = EventBus()
