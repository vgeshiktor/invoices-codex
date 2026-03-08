from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Optional, Sequence


ProviderRunner = Callable[[Optional[List[str]]], int]


@dataclass
class ProviderInvocation:
    module: str
    argv: List[str]
    python_bin: str = "python"

    def to_command(self) -> List[str]:
        return [self.python_bin, "-m", self.module, *self.argv]


@dataclass
class ProviderExecutionResult:
    returncode: int
    error: Optional[str] = None


def resolve_runner(name: str) -> ProviderRunner:
    if name == "gmail":
        from invplatform.cli import gmail_invoice_finder as gmail_finder

        return gmail_finder.run
    if name == "outlook":
        from invplatform.cli import graph_invoice_finder as graph_finder

        return graph_finder.run
    raise ValueError(f"Unknown provider: {name}")


def provider_argv(command: Sequence[str]) -> List[str]:
    if len(command) >= 3 and command[1] == "-m":
        return list(command[3:])
    return list(command)


def invocation_from_command(command: Sequence[str]) -> ProviderInvocation:
    if len(command) >= 3 and command[1] == "-m":
        return ProviderInvocation(
            python_bin=str(command[0]),
            module=str(command[2]),
            argv=list(command[3:]),
        )
    return ProviderInvocation(
        module="",
        argv=list(command),
    )


def execute_provider(
    name: str, invocation_or_command: ProviderInvocation | Sequence[str]
) -> ProviderExecutionResult:
    if isinstance(invocation_or_command, ProviderInvocation):
        argv = list(invocation_or_command.argv)
    else:
        argv = provider_argv(invocation_or_command)
    runner = resolve_runner(name)
    try:
        return ProviderExecutionResult(returncode=int(runner(argv)))
    except SystemExit as exc:
        code = exc.code
        return ProviderExecutionResult(returncode=int(code) if isinstance(code, int) else 1)
    except Exception as exc:  # pragma: no cover - defensive boundary
        return ProviderExecutionResult(returncode=1, error=str(exc))
