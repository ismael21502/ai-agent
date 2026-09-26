# Episode

An **episode** represents the current state of the work being carried out in a conversation.

It is a compact representation of the current context needed to continue the work without relying on the full conversation history.

An episode is **not**:

* A summary of the entire conversation.
* A chronological log of actions.
* A changelog.
* A concatenation of previous episodes and new messages.

Instead, each new episode replaces the previous one with an updated representation of the current state.

## Structure

```json
{
    "topic": "...",
    "summary": "...",
    "relevant_paths": [],
    "last_interaction": {
        "user_request": "...",
        "agent_response": "..."
    }
}
```

### `topic`

Represents the relatively stable subject or activity being worked on.

It should answer:

> What are we working on?

The topic should describe the broader subject rather than the specific action of the current interaction.

Good examples:

```text
"AI Personal Assistant"
"Boat Rental Management System"
"Planning a trip to Japan"
"Organizing a morning routine"
```

Avoid using only the immediate action as the topic:

```text
"Update README"
"Read main.py"
"Fix a bug"
```

Those actions may change while the same episode continues.

---

### `summary`

Represents the **current state of the work**.

It should contain the information necessary to understand and continue the work, including:

* Important decisions.
* Current objectives.
* Progress.
* Relevant context.
* Results that are necessary to continue.
* Other persistent information that is important to the current state of the work.

Definition:

> **Current state of the work: important decisions, objectives, progress, relevant context, and results that are necessary to continue.**

The summary is not a chronological history of what happened.

For example, instead of:

```text
The user asked to review main.py.
main.py was read.
README.md was read.
README.md was modified.
```

the summary should represent the resulting state:

```text
The project documentation is being updated to reflect the current
LangGraph-based architecture. README.md was updated to describe the
current model, tools, execution flow, and memory system. The
documentation should remain aligned with the implementation in main.py.
```

Information from an older interaction should be preserved in the summary when it remains relevant to the current state of the work.

---

### `relevant_paths`

Contains files or directories that are relevant to the current work and may be useful in future interactions.

A path is **not** considered relevant merely because it appeared in a tool result.

During an execution, tools may produce `observed_paths`. These are candidate paths that were explicitly involved in successful tool operations.

The episode process may select some of them as `relevant_paths`.

For example:

```json
[
    {
        "path": "E:/Proyectos/Automation/AI Agent/main.py",
        "explanation": "Contains the main implementation of the agent."
    },
    {
        "path": "E:/Proyectos/Automation/AI Agent/README.md",
        "explanation": "Contains the main project documentation."
    }
]
```

The explanation should describe why the path is relevant to the current work.

Paths should not be inferred from arbitrary file listings. In particular, the contents of `listFiles` or `findFiles` results should not automatically become relevant paths.

---

### `last_interaction`

Represents only the **most recent interaction** that produced the current episode.

```json
{
    "user_request": "...",
    "agent_response": "..."
}
```

#### `user_request`

The user's request from the current interaction.

#### `agent_response`

The agent's final response from the current interaction.

`last_interaction` is replaced when the episode is updated.

Previous interactions should not accumulate inside this field.

If information from a previous interaction remains important, it should be incorporated into `summary`.

---

# Episode Updates

A new episode is generated from:

```text
previous episode
+
current execution
↓
new episode
```

The current execution may contain:

* The current user request.
* The agent's final response.
* Successful tool results.
* Observed paths.
* Other relevant execution information.

Raw execution information is provided as evidence for generating the new episode, but it does not automatically become part of the episode.

The episode is therefore a **semantic compression of the execution**, rather than a literal subset of the messages.

Conceptually:

```text
RAW EXECUTION
      ↓
Information available for reasoning
      ↓
Episode generation
      ↓
COMPACT CURRENT STATE
```

## Information Ownership

Whenever possible, deterministic information should be extracted by code rather than inferred by the LLM.

### Deterministic

The application can provide:

* `user_request`
* `agent_response`
* `observed_paths`
* successful tool results
* the previous `current_episode`

### Semantic

The LLM is responsible for determining:

* `topic`
* `summary`
* which observed paths should become `relevant_paths`

The LLM should not need to reconstruct deterministic information from raw messages when the application can provide it directly.

---

# Observed Paths vs. Relevant Paths

These concepts must remain separate.

### `observed_paths`

Paths that were explicitly involved in successful tool operations during the current execution.

They are execution data.

For example:

```text
main.py
README.md
.
```

An observed path is not necessarily important enough to persist in the episode.

### `relevant_paths`

Paths that remain useful for understanding or continuing the current work.

They are episode state.

The relationship is:

```text
successful tool operations
        ↓
observed_paths
        ↓
semantic selection
        ↓
relevant_paths
```

The `result` of a tool should not be treated as a source of persistent paths merely because it contains filenames or directories.

---

# Persistence Rules

The episode should preserve information according to its importance to the current state of the work.

Information should generally survive an episode update when it is:

* Still valid.
* Relevant to the current work.
* Necessary to continue the work.
* Important for understanding the current state.

Information should generally not be preserved when it is:

* Merely historical.
* A transient implementation detail with no future relevance.
* A completed action that no longer affects the current state.
* Redundant with more current information.
* Only relevant to the previous interaction.

The goal is to maintain **useful state**, not historical completeness.

---

# Example

After an interaction such as:

```text
User:
Review main.py and update README.
```

The execution may contain tool results showing that `main.py` and `README.md` were read and modified.

The resulting episode could be:

```json
{
    "topic": "AI Personal Assistant",

    "summary": "The project documentation is being updated to reflect the current
    LangGraph-based architecture. README.md was updated to describe the current
    model, tools, execution flow, and memory system. The documentation should
    remain aligned with the implementation in main.py.",

    "relevant_paths": [
        {
            "path": "E:/Proyectos/Automation/AI Agent/main.py",
            "explanation": "Contains the main implementation of the agent."
        },
        {
            "path": "E:/Proyectos/Automation/AI Agent/README.md",
            "explanation": "Contains the main project documentation."
        }
    ],

    "last_interaction": {
        "user_request": "Review main.py and update README.",
        "agent_response": "I reviewed main.py and updated README."
    }
}
```

The next interaction should update this state rather than append another summary to it.
