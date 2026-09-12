"""Verifiers v1 plugin: one controller-owned episode per agent attempt."""

import json
import os
from contextlib import asynccontextmanager
from typing import cast

import verifiers.v1 as vf
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam, ChatCompletionToolParam
from pydantic import PrivateAttr, model_validator
from verifiers.v1 import graph
from verifiers.v1.configs.agent import TimeoutConfig
from verifiers.v1.dialects import parse_message
from verifiers.v1.dialects.chat import message_to_wire

from .episode import EpisodeSession, episode_session, native_tools

PLUGIN_ID = "opsforge_verifiers"


def tool_error(message: str) -> dict:
    return {"isError": True, "content": [{"type": "text", "text": message}]}


@asynccontextmanager
async def capture_tail(trace: vf.Trace, messages: list[ChatCompletionMessageParam]):
    try:
        yield
    finally:
        # v0.3.1 checks turn/trace stops before recording the next request. Preserve
        # real, unsampled trailing tool outputs on stop, timeout, and provider error.
        # Prefix matching avoids duplicating messages already recorded by interception.
        graph.prepare_turn(
            trace, [parse_message(dict(m)) for m in messages]
        ).commit_prompt()


class OpsForgeState(vf.State):
    # Not TaskData, tool schemas, trace.info, or any serialized configuration.
    _session: EpisodeSession | None = PrivateAttr(default=None)

    @property
    def session(self) -> EpisodeSession:
        if self._session is None:
            raise RuntimeError("Run OpsForge tasks through OpsForgeEnv")
        return self._session


class OpsForgeTask(vf.Task[vf.TaskData, OpsForgeState]):
    def __init__(self, data, config=None, *, session: EpisodeSession | None = None):
        super().__init__(data, config)
        self._session = session
        self._trace: vf.Trace | None = None

    async def setup(self, trace: vf.Trace, runtime: vf.Runtime) -> None:
        self._trace = trace
        if self._session is None:
            raise RuntimeError("Run OpsForge tasks through OpsForgeEnv")
        assert isinstance(trace.state, OpsForgeState)
        trace.state._session = self._session

    @vf.stop
    async def episode_done(self, trace: vf.Trace) -> bool:
        assert isinstance(trace.state, OpsForgeState)
        return await trace.state.session.terminal()

    async def finalize(self, trace: vf.Trace, runtime: vf.Runtime) -> None:
        assert isinstance(trace.state, OpsForgeState)
        trace.info["opsforge"] = await trace.state.session.finalize()

    @vf.reward
    async def canonical(self, trace: vf.Trace) -> float:
        return float(trace.info["opsforge"]["result"]["reward"])


# v0.3.1's Taskset bound fixes State to the base class despite supporting custom State.
class OpsForgeTaskset(vf.Taskset[OpsForgeTask]):  # pyright: ignore[reportInvalidTypeArguments]
    def load(self):
        # The live reset supplies the authoritative public instruction and policy.
        yield OpsForgeTask(
            vf.TaskData(idx=0, name="identity-group-v1"), self.config.task
        )


class OpsForgeHarness(vf.Harness[vf.HarnessConfig]):
    """Local tool-calling agent; model traffic goes through Verifiers interception.

    No shell execution, shared episode credentials, or automatic tool retries.
    The model is configurable via Verifiers' standard client/model settings.
    """

    APPENDS_SYSTEM_PROMPT = True
    SUPPORTS_MCP = True
    EXECUTES_CODE = False
    NEEDS_CONTAINER = False

    async def launch(
        self,
        ctx: vf.ModelContext,
        trace: vf.Trace,
        runtime: vf.Runtime,
        endpoint: str,
        secret: str,
        mcp_urls: dict[str, str],
        data: vf.TaskData,
    ) -> vf.ProgramResult:
        if mcp_urls:
            raise ValueError(
                "OpsForge uses only its episode-scoped native MCP endpoints"
            )
        assert isinstance(trace.state, OpsForgeState)
        session = trace.state.session
        system, prompt = self.resolve_prompt(data)
        messages: list[ChatCompletionMessageParam] = (
            [{"role": "system", "content": system}] if system else []
        )
        if isinstance(prompt, str):
            messages.append({"role": "user", "content": prompt})
        elif prompt is not None:
            messages.extend(
                cast(ChatCompletionMessageParam, message_to_wire(message))
                for message in prompt
            )
        async with (
            capture_tail(trace, messages),
            native_tools(session.config) as native,
            AsyncOpenAI(base_url=endpoint, api_key=secret, max_retries=0) as model,
        ):
            while True:
                # @stop prevents further model sampling once the episode ends.
                completion = await model.chat.completions.create(
                    model=ctx.model,
                    messages=messages,
                    tools=cast(list[ChatCompletionToolParam], native.tools),
                )
                message = completion.choices[0].message
                messages.append(
                    cast(
                        ChatCompletionMessageParam,
                        message.model_dump(exclude_none=True),
                    )
                )
                if not message.tool_calls:
                    break
                for call in message.tool_calls:
                    if call.type != "function":
                        raise ValueError("OpsForge requires function tool calls")
                    if await session.terminal():
                        result = tool_error(
                            "Episode has ended; no further actions executed."
                        )
                    else:
                        try:
                            arguments = json.loads(call.function.arguments)
                        except json.JSONDecodeError as error:
                            # Invalid agent input is recoverable: explain it to the
                            # agent so it can correct the call on its next turn.
                            result = tool_error(f"Invalid tool JSON: {error.msg}")
                        else:
                            if not isinstance(arguments, dict):
                                result = tool_error(
                                    "Tool arguments must be a JSON object."
                                )
                            elif call.function.name not in native.routes:
                                result = tool_error(
                                    "Unknown tool; use the advertised tool names."
                                )
                            else:
                                result = await native.call(
                                    call.function.name, arguments
                                )
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": call.id,
                            "content": json.dumps(result),
                        }
                    )
        return vf.ProgramResult(exit_code=0, stdout="", stderr="")


class OpsForgeEnvConfig(vf.EnvConfig):
    max_concurrent_agents: int | None = 1
    taskset: vf.TasksetConfig = vf.TasksetConfig(id=PLUGIN_ID)
    base_url: str = "http://127.0.0.1:8000"
    controller_token_var: str = "OPSFORGE_CONTROLLER_TOKEN"
    agent: vf.AgentConfig = vf.AgentConfig(
        runtime=vf.SubprocessConfig(),
        max_turns=30,
        timeout=TimeoutConfig(rollout=300),
    )

    @model_validator(mode="after")
    def check_contract(self):
        if self.agent.runtime.type != "subprocess":
            raise ValueError(
                "OpsForge's in-process harness requires runtime.type=subprocess"
            )
        if self.agent.harness is not None and self.agent.harness.id != PLUGIN_ID:
            raise ValueError("OpsForge requires its authenticated native MCP harness")
        if self.agent.retries.max_retries:
            raise ValueError(
                "Use env.retries, not agent.retries: each retry needs a fresh episode"
            )
        task = self.taskset.task
        if task.rewards or task.judges or task.stops:
            raise ValueError(
                "OpsForge uses mandatory canonical scoring and terminal stops"
            )
        return self


class OpsForgeEnv(vf.Env[OpsForgeEnvConfig]):
    async def run(self, task: vf.Task, agents: vf.Agents) -> None:
        token = os.environ.get(self.config.controller_token_var)
        if not token:
            raise ValueError(f"Set {self.config.controller_token_var}")
        # Verifiers skips Task.finalize for harness/setup errors. Own the controller
        # outside agents.run so *all* exits still finalize and revoke credentials.
        async with episode_session(self.config.base_url, token) as session:
            data = task.data.model_copy(
                update={
                    "prompt": session.config["instruction"],
                    "system_prompt": "\n\n".join(
                        filter(
                            None,
                            [
                                session.config["policy"],
                                task.data.system_prompt,
                            ],
                        )
                    ),
                }
            )
            attempt = OpsForgeTask(data, task.config, session=session)
            try:
                # Same upstream invariant State annotation as Taskset's bound above.
                await agents.agent.run(cast(vf.Task, attempt))
            finally:
                if attempt._trace is not None:
                    try:
                        # Keep diagnostic links even when Verifiers skipped scoring.
                        attempt._trace.info["opsforge"] = await session.finalize()
                    finally:
                        assert isinstance(attempt._trace.state, OpsForgeState)
                        attempt._trace.state._session = None
