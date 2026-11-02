"""ReadOnlyShellExecutor — an allowlist-based ShellTool executor.

Used by 02-05-08-shell-tool-readme-generator.ipynb.
Import with:
    from source.shell_executor import ReadOnlyShellExecutor
"""

import asyncio
import glob
import os
import re
import shlex
from pathlib import Path

from agents import (
    ShellCallOutcome,    # stores whether a command exited normally or timed out
    ShellCommandOutput,  # stores one command's stdout, stderr, and outcome
    ShellCommandRequest, # passed to the executor; contains the commands to run
    ShellResult,         # wraps a list of ShellCommandOutputs; returned to the SDK
)


class ReadOnlyShellExecutor:
    """ShellTool executor that allows only read-only inspection commands.

    ShellTool does not run commands itself — it delegates execution to this
    callable. By defining our own executor we can check every command before
    anything reaches the OS.

    Layers of protection:
    1. No shell — each command is split into words with `shlex` and the
       program is started directly, so pipes, `;`, redirection, `$VARS` and
       sub-shells have no special meaning
    2. `blocked_characters` — commands containing shell syntax are rejected
       outright, so the model gets a clear error instead of odd results
    3. `allowed_programs` — only these programs may run
    4. Option checks — options that write or run other programs
       (`find -delete`/`-exec`, `sed -i`/`w`) are rejected; `sed` may only
       print line ranges
    5. Path checks — every argument that could be a path must stay inside
       `working_folder` (no `~`, `..` escapes or absolute paths elsewhere)
    """

    # Programs the agent may run.
    allowed_programs: frozenset[str] = frozenset({
        'pwd', 'ls', 'find', 'sed', 'head', 'cat', 'grep', 'wc',
        'dir', 'type',  # Windows equivalents (cmd.exe built-ins)
    })

    # Shell syntax that has no place in a simple read-only command.
    blocked_characters: tuple[str, ...] = (
        '|', ';', '&', '>', '<', '`', '$', '(', ')', '{', '}',
        '%', '^', '\n', '\r',
    )

    # find options that delete files, write files or run other programs.
    blocked_find_options: frozenset[str] = frozenset({
        '-delete', '-exec', '-execdir', '-ok', '-okdir',
        '-fprint', '-fprint0', '-fprintf', '-fls',
    })

    # The only sed scripts allowed: print a line range, such as 1,40p or 5p.
    sed_script_pattern = re.compile(r'\d+(,(\d+|\$))?p')

    def __init__(self, working_folder: Path | None = None):
        # All relative paths in shell commands are resolved against this
        # folder, and no command may read outside it. Defaults to the current
        # working directory so notebooks work without extra configuration.
        self.working_folder = Path(working_folder or Path.cwd()).resolve()

    def _inside_working_folder(self, path_text: str) -> bool:
        """Return True if path_text resolves to a location in working_folder."""
        if path_text.startswith('~'):
            return False
        resolved = (self.working_folder / path_text).resolve()
        return resolved.is_relative_to(self.working_folder)

    def parse(self, command: str) -> list[str] | None:
        """Return the command's words if it is allowed, otherwise None."""
        if any(char in command for char in self.blocked_characters):
            return None

        try:
            words = shlex.split(command)
        except ValueError:  # for example, an unclosed quote
            return None

        if not words or words[0] not in self.allowed_programs:
            return None

        program, args = words[0], words[1:]

        if program == 'find' and self.blocked_find_options.intersection(args):
            return None

        if program == 'sed':
            # Allow only: sed -n 'START,ENDp' FILE...
            if len(args) < 3 or args[0] != '-n':
                return None
            if not self.sed_script_pattern.fullmatch(args[1]):
                return None
            if any(arg.startswith('-') for arg in args[2:]):
                return None

        # Check every argument that could name a file. For --option=value,
        # check the value. Patterns such as grep's search text are checked
        # too; they just resolve to a harmless name inside the folder.
        for arg in args:
            if arg.startswith('-'):
                if '=' not in arg:
                    continue
                arg = arg.split('=', 1)[1]
            if not self._inside_working_folder(arg):
                return None

        return words

    def is_allowed(self, command: str) -> bool:
        """Return True only for simple, read-only inspection commands."""
        return self.parse(command) is not None

    def _expand_globs(self, words: list[str]) -> list[str]:
        """Expand wildcards like *.py, as a shell would, inside working_folder.

        find and grep receive their patterns unchanged. A wildcard that
        matches nothing is passed through as-is, like bash does.
        """
        program = words[0]
        if program in ('find', 'dir'):
            return words

        expanded = [program]
        pattern_seen = program != 'grep'  # grep's first plain argument is its pattern

        for arg in words[1:]:
            if arg.startswith('-') or not any(c in arg for c in '*?['):
                if not arg.startswith('-'):
                    pattern_seen = True
                expanded.append(arg)
                continue
            if not pattern_seen:
                pattern_seen = True
                expanded.append(arg)
                continue
            matches = sorted(glob.glob(arg, root_dir=self.working_folder))
            expanded.extend(matches or [arg])

        return expanded

    async def __call__(self, request: ShellCommandRequest) -> ShellResult:
        """Execute approved commands; return a blocked-command error for others.

        The SDK calls this method after ShellTool decides to run a shell
        command. For each command in the request we either run it in a
        subprocess or return a synthetic error, then wrap all results in a
        ShellResult for the SDK to forward to the model.
        """
        action = request.data.action
        command_outputs: list[ShellCommandOutput] = []

        for command in action.commands:
            words = self.parse(command)
            if words is None:
                # Return a synthetic error rather than running the command.
                # Exit code 126 means "command not executable" by POSIX convention.
                command_outputs.append(ShellCommandOutput(
                    command=command,
                    stdout='',
                    # Tell the model *why* and what it may do instead, so it
                    # can recover in one step instead of guessing.
                    stderr=(
                        'Blocked by ReadOnlyShellExecutor. Run ONE simple '
                        'command per call: no pipes (|), no ; or && chaining, '
                        'no redirection, no $variables. Allowed commands: pwd, '
                        'ls, find, head, cat, sed -n START,ENDp, grep, wc. '
                        'Paths must stay inside the working folder.'
                    ),
                    outcome=ShellCallOutcome(type='exit', exit_code=126),
                ))
                continue

            argv = self._expand_globs(words)
            if os.name == 'nt' and argv[0] in ('dir', 'type'):
                argv = ['cmd', '/c', *argv]  # built into cmd.exe, not programs

            # Start the program directly (no shell). `env=os.environ.copy()`
            # ensures PATH is inherited so programs like `find` are found.
            try:
                process = await asyncio.create_subprocess_exec(
                    *argv,
                    cwd=self.working_folder,
                    env=os.environ.copy(),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
            except FileNotFoundError:
                command_outputs.append(ShellCommandOutput(
                    command=command,
                    stdout='',
                    stderr=f'{argv[0]}: command not found on this system',
                    outcome=ShellCallOutcome(type='exit', exit_code=127),
                ))
                continue

            try:
                # Enforce a 10-second timeout so a slow command cannot stall
                # the agent run indefinitely.
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), timeout=10
                )
                outcome = ShellCallOutcome(type='exit', exit_code=process.returncode)
            except asyncio.TimeoutError:
                process.kill()
                stdout, stderr = await process.communicate()
                # 'timeout' tells the model the command was killed, not that
                # it completed — the model can retry with a narrower scope.
                outcome = ShellCallOutcome(type='timeout', exit_code=None)

            command_outputs.append(ShellCommandOutput(
                command=command,
                stdout=stdout.decode('utf-8', errors='replace'),
                stderr=stderr.decode('utf-8', errors='replace'),
                outcome=outcome,
            ))

        return ShellResult(
            output=command_outputs,
            provider_data={'working_folder': str(self.working_folder)},
        )
