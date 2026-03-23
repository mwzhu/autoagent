def reset_state(state):
    state["status"] = "idle"
    if "errors" in state:
        state["errors"] = []
    return state
