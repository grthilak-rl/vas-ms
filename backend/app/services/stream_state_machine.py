"""Stream state machine for managing stream lifecycle."""
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.models.stream import Stream, StreamState
from app.models.stream_state_transition import StreamStateTransition


class StreamStateMachine:
    """
    Finite State Machine for stream lifecycle management.

    State transitions:
    - None → INITIALIZING (stream creation)
    - INITIALIZING → READY (SSRC captured, producer created)
    - READY → LIVE (FFmpeg started, RTP flowing)
    - LIVE → ERROR (FFmpeg crash, RTP timeout)
    - ERROR → LIVE (auto-restart succeeded)
    - LIVE → STOPPED (manual stop)
    - STOPPED → CLOSED (cleanup complete)
    - Any → ERROR (exceptional failure)
    """

    # Valid state transitions
    VALID_TRANSITIONS = {
        None: [StreamState.INITIALIZING],
        StreamState.INITIALIZING: [StreamState.READY, StreamState.ERROR],
        StreamState.READY: [StreamState.LIVE, StreamState.ERROR],
        StreamState.LIVE: [StreamState.ERROR, StreamState.STOPPED],
        StreamState.ERROR: [StreamState.LIVE, StreamState.STOPPED, StreamState.CLOSED],
        StreamState.STOPPED: [StreamState.LIVE, StreamState.CLOSED],  # Allow restart
        StreamState.CLOSED: [],  # Terminal state
    }

    async def transition(
        self,
        stream: Stream,
        to_state: StreamState,
        reason: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        db: AsyncSession = None
    ) -> bool:
        """
        Transition a stream to a new state.

        Args:
            stream: Stream object to transition
            to_state: Target state
            reason: Human-readable reason for transition
            metadata: Additional context
            db: Database session (for audit log)

        Returns:
            True if transition was valid and executed

        Raises:
            ValueError: If transition is invalid
        """
        from_state = stream.state

        # Validate transition
        if not self.is_valid_transition(from_state, to_state):
            raise ValueError(
                f"Invalid state transition: {from_state} → {to_state}. "
                f"Valid transitions from {from_state}: {self.VALID_TRANSITIONS.get(from_state, [])}"
            )

        # Update stream state
        old_state_value = from_state.value if from_state else None
        stream.state = to_state

        logger.info(
            f"Stream {stream.id} transition: {old_state_value} → {to_state.value} "
            f"(reason: {reason or 'none'})"
        )

        # Create audit log
        if db:
            transition_record = StreamStateTransition(
                stream_id=stream.id,
                from_state=old_state_value,
                to_state=to_state.value,
                reason=reason,
                metadata=metadata or {}
            )
            db.add(transition_record)

        return True

    def is_valid_transition(
        self,
        from_state: Optional[StreamState],
        to_state: StreamState
    ) -> bool:
        """
        Check if a state transition is valid.

        Args:
            from_state: Current state (None for initial creation)
            to_state: Target state

        Returns:
            True if transition is valid
        """
        valid_targets = self.VALID_TRANSITIONS.get(from_state, [])
        return to_state in valid_targets

    def get_valid_transitions(self, from_state: Optional[StreamState]) -> list:
        """
        Get list of valid target states from current state.

        Args:
            from_state: Current state

        Returns:
            List of valid target states
        """
        return self.VALID_TRANSITIONS.get(from_state, [])

    def is_terminal_state(self, state: StreamState) -> bool:
        """
        Check if a state is terminal (no outgoing transitions).

        Args:
            state: State to check

        Returns:
            True if terminal state
        """
        return len(self.VALID_TRANSITIONS.get(state, [])) == 0

    def can_accept_consumers(self, state: StreamState) -> bool:
        """
        Check if stream can accept consumers in the given state.

        Args:
            state: Stream state

        Returns:
            True if consumers can attach
        """
        return state == StreamState.LIVE

    def requires_cleanup(self, state: StreamState) -> bool:
        """
        Check if stream requires cleanup (FFmpeg, producer, etc.).

        Args:
            state: Stream state

        Returns:
            True if cleanup is needed
        """
        return state in [StreamState.STOPPED, StreamState.ERROR, StreamState.CLOSED]


# Global state machine instance
stream_state_machine = StreamStateMachine()


# Module-level convenience function
async def transition(
    stream: Stream,
    to_state: StreamState,
    reason: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    db: AsyncSession = None
) -> bool:
    """
    Module-level convenience function for state transitions.

    Delegates to the global stream_state_machine instance.
    """
    return await stream_state_machine.transition(stream, to_state, reason, metadata, db)
